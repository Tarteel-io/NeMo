# Copyright (c) 2021, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
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

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from omegaconf.omegaconf import MISSING, DictConfig, OmegaConf

from nemo.collections.nlp.data.token_classification.punctuation_capitalization_dataset import (
    PunctuationCapitalizationEvalDataConfig,
    PunctuationCapitalizationTrainDataConfig,
    legacy_data_config_to_new_data_config,
)
from nemo.core.config import TrainerConfig
from nemo.core.config.modelPT import NemoConfig, OptimConfig, SchedConfig
from nemo.utils.exp_manager import ExpManagerConfig


@dataclass
class PunctuationCapitalizationSchedConfig(SchedConfig):
    """
    A configuration of learning rate scheduler. This config is a part of :class:`PunctuationCapitalizationOptimConfig`
    config.

    Warmup is a period in the beginning of training during which
    learning rate is increased linearly to its initial value.
    """

    name: str = 'InverseSquareRootAnnealing'
    """A name of learning rate scheduler. For possible options see :ref:`core/core:Learning Rate Schedulers`."""

    warmup_steps: Optional[int] = None
    """Number of steps spent on warmup. You may specify at most one of parameters ``warmup_steps`` and
    ``warmup_ratio``."""

    warmup_ratio: Optional[float] = None
    """The fraction of training steps spend on warmup. You may specify at most one of parameters ``warmup_steps`` and
    ``warmup_ratio``."""

    last_epoch: int = -1
    """A number of an epoch from which to resume scheduling. Useful when restoring from checkpoint. See more in PyTorch
    documentation. If ``-1``, then start scheduling from the beginning."""


# TODO: support more optimizers (it pins the optimizer to Adam-like optimizers).
@dataclass
class PunctuationCapitalizationOptimConfig(OptimConfig):
    """
    A structure and default values of optimization configuration of punctuation and capitalization model.
    
    This config is a part of :class:`PunctuationCapitalizationModelConfig` config.
    """

    name: str = 'adam'
    "A name of an optimizer. For possible options see :ref:`core/core:Optimizers`."

    lr: float = 1e-3
    """An initial learning rate value. If warmup is used, then ``lr`` is a learning rate after warmup."""

    betas: Tuple[float, float] = (0.9, 0.98)
    """An Adam optimizer momentum parameters."""

    weight_decay: float = 0.0
    """A weight decay for L2 regularization."""

    sched: Optional[PunctuationCapitalizationSchedConfig] = PunctuationCapitalizationSchedConfig()
    """A configuration of learning rate scheduler."""


@dataclass
class TokenizerConfig:
    """A structure and default values of source text tokenizer."""

    vocab_file: Optional[str] = None
    """A path to vocabulary file which is used in ``'word'``, ``'char'``, and HuggingFace tokenizers"""

    tokenizer_name: str = MISSING
    """A name of the tokenizer used for tokenization of source sequences. Possible options are ``'sentencepiece'``,
    ``'word', ``'char'``, HuggingFace tokenizers (e.g. ``'bert-base-uncased'``). For more options see function
    ``nemo.collections.nlp.modules.common.get_tokenizer``. The tokenizer must have properties ``cls_id``, ``pad_id``,
    ``sep_id``, ``unk_id``."""

    special_tokens: Optional[Dict[str, str]] = None
    """A dictionary with special tokens passed to constructors of ``'char'``, ``'word'``, ``'sentencepiece'``, and
    various HuggingFace tokenizers."""

    tokenizer_model: Optional[str] = None
    """A path to tokenizer model required for ``'sentencepiece'`` tokenizer."""


@dataclass
class LanguageModelConfig:
    """
    A structure and default values of language model configuration of punctuation and capitalization model. BERT like
    HuggingFace models are supported. Provide a valid ``pretrained_model_name`` and optionally you may
    reinitialize model using ``config_file`` or ``config``.

    Alternatively you can initialize language model using ``lm_checkpoint``.

    This config is a part of :class:`PunctuationCapitalizationModelConfig` config.
    """

    pretrained_model_name: str = MISSING
    """A mandatory name of HuggingFace pretrained model. For example, ``'bert-base-uncased'``."""

    config_file: Optional[str] = None
    """A path to a file with HuggingFace model config which is used to reinitialize language model."""

    config: Optional[Dict] = None
    """A HuggingFace config which is used to reinitialize language model."""

    lm_checkpoint: Optional[str] = None
    """A path to torch checkpoint of a language model."""


@dataclass
class HeadConfig:
    """
    A structure and default values of configuration of capitalization or punctuation model head. This config defines a
    multilayer perceptron which is applied to outputs of a language model. Number of units in the hidden layer is equal
    to the dimension of the language model.

    This config is a part of :class:`PunctuationCapitalizationModelConfig` config.
    """

    num_fc_layers: int = 1
    """A number of hidden layers in a head."""

    fc_dropout: float = 0.1
    """A dropout used in an MLP."""

    activation: str = 'relu'
    """An activation used in hidden layers."""

    use_transformer_init: bool = True
    """Whether to initialize the weights of the classifier head with the same approach used in a language model."""


@dataclass
class ClassLabelsConfig:
    """
    A structure and default values of a mandatory part of config which contains names of files which are saved in .nemo
    checkpoint. These files can also be used for passing label vocabulary to the model. For using them as label
    vocabularies you will need to provide path these files in parameter
    ``model.common_dataset_parameters.label_vocab_dir``.

    This config is a part of :class:`~CommonDatasetParametersConfig`.
    """

    punct_labels_file: str = MISSING
    """A name of punctuation labels file."""

    capit_labels_file: str = MISSING
    """A name of capitalization labels file."""


@dataclass
class CommonDatasetParametersConfig:
    """
    A structure and default values of common dataset parameters cofnig which include label and loss mask information.
    If you omit parameters ``punct_label_ids``, ``capit_label_ids``, ``label_vocab_dir``, then labels can be inferred
    from training dataset or loaded from checkpoint.

    Parameters ``ignore_extra_tokens`` and ``ignore_start_end`` are responsible for forming loss mask. A loss mask
    defines on which tokens loss is computed.

    This parameter is a part of config :class:`~PunctuationCapitalizationModelConfig`.
    """

    pad_label: str = MISSING
    """A mandatory parameter which should contain label used for padding both for punctuation and capitalization. It
    also serves as a neutral label for both punctuation and capitalization. If any parameter of ``punct_label_ids``,
    ``capit_label_ids`` is provided, then ``pad_label`` must have ``0`` id in then. In addition, if ``label_vocab_dir``
    is provided, then ``pad_label`` has to have ``0`` in ``class_labels.punct_labels_file`` and
    ``class_labels.capit_labels_file``."""

    ignore_extra_tokens: bool = False
    """Whether to compute loss on not first tokens in words. If this parameter is ``True``, then loss mask is ``False``
    all tokens in a word except the first."""

    ignore_start_end: bool = True
    """If ``False``, then loss is computed on [CLS] and [SEP] tokens."""

    punct_label_ids: Optional[Dict[str, int]] = None
    """A dictionary with punctuation label ids. ``pad_label`` must have ``0`` id in this dictionary. You can omit this
    parameter and pass label ids through ``class_labels.punct_labels_file`` or let model to infer label ids from
    dataset or load them from checkpoint."""

    capit_label_ids: Optional[Dict[str, int]] = None
    """A dictionary with capitalization label ids. ``pad_label`` must have ``0`` id in this dictionary. You can omit
    this parameter and pass label ids through ``class_labels.capit_labels_file`` or let model to infer label ids from
    dataset or load them from checkpoint."""

    label_vocab_dir: Optional[str] = None
    """A path to directory which contains class labels files. See :class:`ClassLabelsConfig`. If this parameter is
    provided, then labels will be loaded from files which are located in ``label_vocab_dir`` and have names specified
    in ``model.class_labels`` configuration section."""


@dataclass
class PunctuationCapitalizationModelConfig:
    """
    A configuration of
    :class:`~nemo.collections.nlp.models.token_classification.punctuation_capitalization_model.PunctuationCapitalizationModel`
    model.

    See an example of model config in
    `nemo/examples/nlp/token_classification/conf/punctuation_capitalization_config.yaml <https://github.com/NVIDIA/NeMo/blob/main/examples/nlp/token_classification/conf/punctuation_capitalization_config.yaml>`_

    This config is a part of :class:`~PunctuationCapitalizationConfig`.
    """

    class_labels: ClassLabelsConfig = ClassLabelsConfig()
    """A mandatory dictionary which contains names of label id files in for .nemo checkpoints. It also can be used for
    passing label vocabularies to the model. If you wish to use ``class_label`` for passing vocabularies, please
    provide path to vocabulary files in ``common_dataset_parameters.label_vocab_dir`` parameter."""

    common_dataset_parameters: Optional[CommonDatasetParametersConfig] = CommonDatasetParametersConfig()
    """A dictionary with label information. It also contains ``ignore_start_end`` and ``ignore_extra_tokens``
    parameters which are responsible for loss mask creation."""

    train_ds: Optional[PunctuationCapitalizationTrainDataConfig] = PunctuationCapitalizationTrainDataConfig(
        use_tarred_dataset=MISSING, tokens_in_batch=MISSING
    )
    """A configuration for creating training dataset and data loader."""

    validation_ds: Optional[PunctuationCapitalizationEvalDataConfig] = PunctuationCapitalizationEvalDataConfig(
        use_tarred_dataset=MISSING, tokens_in_batch=MISSING
    )
    """A configuration for creating validation datasets and data loaders."""

    test_ds: Optional[PunctuationCapitalizationEvalDataConfig] = PunctuationCapitalizationEvalDataConfig(
        use_tarred_dataset=MISSING, tokens_in_batch=MISSING
    )
    """A configuration for creating test datasets and data loaders."""

    punct_head: HeadConfig = HeadConfig()
    """A configuration for creating punctuation MLP head that is applied to a language model outputs."""

    capit_head: HeadConfig = HeadConfig()
    """A configuration for creating capitalization MLP head that is applied to a language model outputs."""

    tokenizer: Any = TokenizerConfig()
    """A configuration for source text tokenizer."""

    language_model: LanguageModelConfig = LanguageModelConfig()
    """A configuration of a BERT like language model which serves as a model body."""

    optim: Optional[OptimConfig] = PunctuationCapitalizationOptimConfig()
    """A configuration of optimizer and learning rate scheduler."""


@dataclass
class PunctuationCapitalizationConfig(NemoConfig):
    """
    A config for punctuation model training and testing.

    See an example of full config in
    `nemo/examples/nlp/token_classification/conf/punctuation_capitalization_config.yaml
    <https://github.com/NVIDIA/NeMo/blob/main/examples/nlp/token_classification/conf/punctuation_capitalization_config.yaml>`_
    """

    pretrained_model: Optional[str] = None
    """Can be an NVIDIA's NGC cloud model or a path to a .nemo checkpoint. You can get list of possible cloud options
    by calling method
    :meth:`~nemo.collections.nlp.models.token_classification.punctuation_capitalization_model.PunctuationCapitalizationModel.list_available_models`.
    """

    name: Optional[str] = 'Punctuation_and_Capitalization'
    """A name of the model. Used for naming output directories."""

    do_training: bool = True
    """Whether to perform training of the model."""

    do_testing: bool = False
    """Whether ot perform testing of the model."""

    model: PunctuationCapitalizationModelConfig = PunctuationCapitalizationModelConfig()
    """A configuration for the
    :class:`~nemo.collections.nlp.models.token_classification.punctuation_capitalization_model.PunctuationCapitalizationModel`
    model."""

    trainer: Optional[TrainerConfig] = TrainerConfig()
    """Contains ``Trainer`` Lightning class constructor parameters."""

    exp_manager: Optional[ExpManagerConfig] = ExpManagerConfig(name=name, files_to_copy=[])
    """A configuration various NeMo training options such as output directories, resuming from checkpoint, tensorboard
    and W&B logging, and so on. For possible options see :ref:`core/core:Experiment Manager`."""


def is_legacy_model_config(model_cfg: DictConfig) -> bool:
    """
    Test if model config is old style config. Old style configs are configs which were used before
    ``common_dataset_parameters`` item was added. Old style datasets use ``dataset`` instead of
    ``common_dataset_parameters``, ``batch_size`` instead of ``tokens_in_batch``. Old style configs do not support
    tarred datasets.

    Args:
        model_cfg: model configuration

    Returns:
        whether ``model_config`` is legacy
    """
    return 'common_dataset_parameters' not in model_cfg


def legacy_model_config_to_new_model_config(model_cfg: DictConfig) -> DictConfig:
    """
    Transform old style config into
    :class:`~nemo.collections.nlp.models.token_classification.punctuation_capitalization_config.PunctuationCapitalizationModelConfig`.
    Old style configs are configs which were used before ``common_dataset_parameters`` item was added. Old style
    datasets use ``dataset`` instead of ``common_dataset_parameters``, ``batch_size`` instead of ``tokens_in_batch``.
    Old style configs do not support tarred datasets.

    Args:
        model_cfg: old style config

    Returns:
        model config which follows dataclass
            :class:`~nemo.collections.nlp.models.token_classification.punctuation_capitalization_config.PunctuationCapitalizationModelConfig`
    """
    train_ds = model_cfg.get('train_ds')
    validation_ds = model_cfg.get('validation_ds')
    test_ds = model_cfg.get('test_ds')
    dataset = model_cfg.dataset
    punct_head_config = model_cfg.get('punct_head', {})
    capit_head_config = model_cfg.get('capit_head', {})
    return OmegaConf.structured(
        PunctuationCapitalizationModelConfig(
            class_labels=model_cfg.class_labels,
            common_dataset_parameters=CommonDatasetParametersConfig(
                pad_label=dataset.pad_label,
                ignore_extra_tokens=dataset.get(
                    'ignore_extra_tokens', CommonDatasetParametersConfig.ignore_extra_tokens
                ),
                ignore_start_end=dataset.get('ignore_start_end', CommonDatasetParametersConfig.ignore_start_end),
                punct_label_ids=model_cfg.punct_label_ids,
                capit_label_ids=model_cfg.capit_label_ids,
            ),
            train_ds=None
            if train_ds is None
            else legacy_data_config_to_new_data_config(train_ds, dataset, train=True),
            validation_ds=None
            if validation_ds is None
            else legacy_data_config_to_new_data_config(validation_ds, dataset, train=False),
            test_ds=None if test_ds is None else legacy_data_config_to_new_data_config(test_ds, dataset, train=False),
            punct_head=HeadConfig(
                num_fc_layers=punct_head_config.get('punct_num_fc_layers', HeadConfig.num_fc_layers),
                fc_dropout=punct_head_config.get('fc_dropout', HeadConfig.fc_dropout),
                activation=punct_head_config.get('activation', HeadConfig.activation),
                use_transformer_init=punct_head_config.get('use_transformer_init', HeadConfig.use_transformer_init),
            ),
            capit_head=HeadConfig(
                num_fc_layers=capit_head_config.get('capit_num_fc_layers', HeadConfig.num_fc_layers),
                fc_dropout=capit_head_config.get('fc_dropout', HeadConfig.fc_dropout),
                activation=capit_head_config.get('activation', HeadConfig.activation),
                use_transformer_init=capit_head_config.get('use_transformer_init', HeadConfig.use_transformer_init),
            ),
            tokenizer=model_cfg.tokenizer,
            language_model=model_cfg.language_model,
            optim=model_cfg.optim,
        )
    )
