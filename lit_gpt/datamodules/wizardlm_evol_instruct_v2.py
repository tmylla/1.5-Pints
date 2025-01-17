from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union, TypedDict, Literal
from datasets import load_dataset, Dataset

from lit_gpt.prompts import PromptStyle
from lit_gpt.datamodules.base import DataModule
from lit_gpt.datamodules.sft_dataset_base import SFTDataset
from lit_gpt.tokenizer import Tokenizer
from lit_gpt.datamodules.typings.formatted_dataset import (
    FormattedSFTSingleturnConversation,
    FormattedSFTSingleturnDataset,
)

HUGGINGFACE_ID = 'WizardLM/WizardLM_evol_instruct_V2_196k'
DOWNLOAD_DIR = './data/sft/wizardlm-evol-instruct-v2'
SPLIT = ['train']

class PreparedWizardLMEvolInstructV2(TypedDict):
    train_dataset: SFTDataset
    val_dataset: None
    test_dataset: None


# Use declarative syntax as 'from' will not be allowed using class syntax
WizardLMEvolInstructV2Conversations = List[
    TypedDict(
        'WizardLMEvolInstructV2Conversations',
        {'from': Literal['human', 'gpt'], 'value': str},
    )
]


class WizardLMEvolInstructV2Row(TypedDict):
    conversations: WizardLMEvolInstructV2Conversations
    idx: str


@dataclass
class WizardLMEvolInstructV2(DataModule):
    """WizardLMEvolInstructV2 data module for supervised finetuning."""

    """Whether to include multi-turn conversations in the dataset."""
    include_multiturn_conversations: bool = False
    """The directory in which the downloaded dataset gets saved."""
    download_dir: Path = Path(DOWNLOAD_DIR)
    """The repo from where the data is downloaded"""
    repo_id: str = HUGGINGFACE_ID

    tokenizer: Optional[Tokenizer] = field(default=None, init=False, repr=False)
    # `batch_size` has no use anymore, as the dataloaders are moved outside
    # in order to support training with multiple SFT datasets at one go.
    batch_size: int = field(default=1, init=False, repr=False)
    max_seq_length: int = field(default=-1, init=False, repr=False)
    train_dataset: Optional[SFTDataset] = field(default=None, init=False, repr=False)
    test_dataset: Optional[SFTDataset] = field(default=None, init=False, repr=False)

    def __init__(self, prompt_style='chatml', num_workers: Optional[int] = None):
        super().__init__()
        self.prompt_style = PromptStyle.from_name(prompt_style)
        if num_workers:
            self.num_workers = num_workers

    def connect(
        self,
        tokenizer: Optional[Tokenizer] = None,
        batch_size: int = 1,
        max_seq_length: Optional[int] = None,
    ) -> None:
        self.tokenizer = tokenizer
        self.batch_size = batch_size
        self.max_seq_length = -1 if max_seq_length is None else max_seq_length

    def prepare_data(self) -> List[Dataset]:
        return load_dataset(
            self.repo_id,
            split=SPLIT,
            cache_dir=self.download_dir,
            streaming=False,
        )

    def setup(self, stage: str = '') -> PreparedWizardLMEvolInstructV2:
        dataset = self.prepare_data()

        train_data = format_dataset(dataset[0], self.include_multiturn_conversations)
        # TODO: WizardLMEvolInstructV2 doesn't have test_data. We can split it out from the train_data
        # test_data = format_dataset(dataset[1], self.include_multiturn_conversations)

        self.train_dataset = SFTDataset(
            data=train_data,
            tokenizer=self.tokenizer,
            prompt_style=self.prompt_style,
            max_seq_length=self.max_seq_length,
            mask_prompt=self.mask_prompt,
            ignore_index=self.ignore_index,
        )
        # self.test_dataset = SFTDataset(
        #     data=test_data,
        #     tokenizer=self.tokenizer,
        #     prompt_style=self.prompt_style,
        #     max_seq_length=self.max_seq_length,
        #     mask_prompt=self.mask_prompt,
        #     ignore_index=self.ignore_index,
        # )

        return {
            'train_dataset': self.train_dataset,
            'val_dataset': self.test_dataset,
            'test_dataset': self.test_dataset,
        }


def format_dataset(
    dataset: List[WizardLMEvolInstructV2Row],
    # `include_multi_turn_conversations` kept for backward compatibility with litgpt
    include_multi_turn_conversations=False,
) -> FormattedSFTSingleturnDataset:
    formatted: FormattedSFTSingleturnDataset = []

    for entry in dataset:
        conversation = entry['conversations']

        human_message = conversation[0]
        if human_message['from'] != 'human':
            print(
                f'WARN: WizardLM row[{entry["idx"]}] is corrupted. Expected role to be `user`, but is `{human_message["from"]}` instead.'
            )

        ai_message = conversation[1]
        if ai_message['from'] != 'gpt':
            print(
                f'WARN: WizardLM row[{entry["idx"]}] is corrupted. Expected role to be `assistant`, but is `{ai_message["from"]}` instead.'
            )

        formatted_sft_dict: FormattedSFTSingleturnConversation = {
            'instruction': human_message['value'],
            'input': '',
            'output': ai_message['value'],
        }
        formatted.append(formatted_sft_dict)

    return formatted
