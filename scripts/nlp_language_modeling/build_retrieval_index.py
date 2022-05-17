# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
"""
import argparse
import multiprocessing

import faiss
from sentence_transformers import SentenceTransformer

from nemo.collections.nlp.data.language_modeling.megatron.indexed_retrieval_dataset import MMapRetrievalIndexedDataset
from nemo.collections.nlp.modules.common.tokenizer_utils import get_nmt_tokenizer
from nemo.utils import logging

queue = multiprocessing.Queue(10)
emb_queue = multiprocessing.Queue(10)


def process_sentence_chunks(ds: MMapRetrievalIndexedDataset, tokenizer, chunk_size: int, warm_up_size: int):
    total_chunks = ds.chunks
    warm_up_slices = ds.get_chunk(slice(0, warm_up_size), force_no_padding=True)
    sentences = [tokenizer.ids_to_text(ids) for ids in warm_up_slices]
    queue.put(sentences)

    start = warm_up_size
    threshold = 0.1
    while start < total_chunks:
        if start / total_chunks > threshold:
            logging.info(f"sentence processing {start / total_chunks} is done")
            threshold += 0.1
        id_slices = ds.get_chunk(slice(start, min(start + chunk_size, total_chunks)), force_no_padding=True)
        start = min(start + chunk_size, total_chunks)
        sentences = [tokenizer.ids_to_text(ids) for ids in id_slices]
        queue.put(sentences)
    queue.put(None)


def get_sentence_chunks():
    return queue.get()


def calculate_embedding(pool, batch_size):
    while True:
        sentences = get_sentence_chunks()
        if sentences is None:
            break
        emb = model.encode_multi_process(sentences=sentences, pool=pool, batch_size=batch_size)
        emb_queue.put(emb)
    emb_queue.put(None)


def get_emb():
    return emb_queue.get()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="build Faiss index",)
    parser.add_argument(
        '--input_file', type=str, required=True, help='Input file',
    )
    parser.add_argument(
        '--train_index_size', type=int, required=True, help='The number of sentences that is used to train the index',
    )
    parser.add_argument(
        '--train_chunk_size', type=int, default=10000, help='The sentences in chunks that is added to the index',
    )
    parser.add_argument(
        '--sentence_transformer_model',
        type=str,
        default='bert-base-nli-mean-tokens',
        help='sentence transformer to load',
    )
    parser.add_argument(
        '--output_file', type=str, required=True, help='Output Faiss index file',
    )
    parser.add_argument(
        '--devices', type=str, default=None, help='delimited list input with cuda devices. Specify like 0,1,2'
    )
    parser.add_argument(
        "--batch_size", type=int, default=4000, help="Batch size for encoding. Use max according to GPU MEM"
    )
    parser.add_argument("--subquantizers", type=int, default=8, help="Quantizer code size")
    group = parser.add_argument_group(title='tokenizer')
    group.add_argument(
        '--tokenizer-library',
        type=str,
        required=True,
        choices=['yttm', 'sentencepiece', 'megatron', 'huggingface', 'tabular'],
        help='What tokenizer library to use.',
    )
    group.add_argument(
        '--tokenizer-type', type=str, default=None, help='What type of tokenizer to use.',
    )
    group.add_argument(
        '--tokenizer-model', type=str, default=None, help='Path to tokenizer model.',
    )
    group.add_argument('--vocab-file', type=str, default=None, help='Path to the vocab file')
    group.add_argument('--merge-file', type=str, default=None, help='Path to the BPE merge file (if necessary).')
    group.add_argument('--delimiter', type=str, default=None, help='delimiter used for tabular tokenizer')

    args = parser.parse_args()
    model = SentenceTransformer(args.sentence_transformer_model)
    tokenizer = get_nmt_tokenizer(
        library=args.tokenizer_library,
        model_name=args.tokenizer_type,
        tokenizer_model=args.tokenizer_model,
        vocab_file=args.vocab_file,
        merges_file=args.merge_file,
        delimiter=args.delimiter,
    )

    ds = MMapRetrievalIndexedDataset(args.input_file)
    # make sure the dataset is padded as retrieval database
    assert ds._index.retrieval_db
    if ds.chunks < args.train_index_size:
        raise ValueError(
            f"the train index size {args.train_index_size} is larger than the total number of chunks {ds.chunks} in the dataset"
        )

    process = multiprocessing.Process(
        target=process_sentence_chunks, args=(ds, tokenizer, args.train_chunk_size, args.train_index_size)
    )
    process.start()

    if args.devices is None:
        device_list = None
    else:
        device_list = ['cuda:' + str(device) for device in args.devices.split(',')]

    pool = model.start_multi_process_pool(device_list)

    emb_process = multiprocessing.Process(
        target=calculate_embedding, args=(pool, args.batch_size)
    )
    emb_process.start()

    # get first batch of sentences to build up the index
    # sentences = get_sentence_chunks()

    emb = get_emb()

    nlist = 100
    # m is number of subquantizers. So vector of size D is broken into m sub-vectors of size D/m
    m = args.subquantizers
    k = 4  # num_nearest neighbors to get
    quantizer = faiss.IndexFlatIP(emb.shape[1])
    index = faiss.IndexIVFPQ(quantizer, emb.shape[1], nlist, m, 8)
    # 8 specifies that each sub-vector is encoded as 8 bits
    # build the index
    index.train(emb)
    logging.info('Trained Index')

    # add the first batch to the index
    index.add(emb)

    while True:
        emb = get_emb()
        if emb is None:
            break
        index.add(emb)
    process.join()
    emb_process.join()
    logging.info('Writing Index file')
    faiss.write_index(index, args.output_file)
    logging.info(f'Size of Index : {index.ntotal}')
    model.stop_multi_process_pool(pool)

