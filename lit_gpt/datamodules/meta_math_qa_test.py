from json import loads
from lit_gpt.datamodules.meta_math_qa import format_dataset

MOCK_DATA = []

with open(
    './lit_gpt/datamodules/meta_math_qa_test.jsonl', 'r', encoding='utf-8'
) as jsonl_file:
    for line in jsonl_file:
        MOCK_DATA.append(loads(line))


def test_metamath_format_dataset():
    train_data = format_dataset(dataset=MOCK_DATA)

    train_data_row_one = train_data[0]
    mock_data_row_one = MOCK_DATA[0]

    # The instruction and output pair in train_data is made
    # from `content` from the nth and nth+1 row in `messages``
    assert mock_data_row_one['query'] == train_data_row_one['instruction']
    assert mock_data_row_one['response'] == train_data_row_one['output']