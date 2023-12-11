# coding=utf-8
# Copyright 2023 The TensorFlow Datasets Authors.
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

r"""`tfds convert_format` command."""

from collections.abc import Iterator
import dataclasses
from typing import Type

from etils import epath
from tensorflow_datasets.core import dataset_info
from tensorflow_datasets.core import file_adapters
from tensorflow_datasets.core import naming
from tensorflow_datasets.core import splits as splits_lib
from tensorflow_datasets.core.utils import type_utils


@dataclasses.dataclass(frozen=True)
class ShardInstruction:
  """Instruction for how one single shard should be converted."""

  in_path: epath.Path
  in_file_adapter: Type[file_adapters.FileAdapter]
  out_path: epath.Path
  out_file_adapter: Type[file_adapters.FileAdapter]

  def convert(self) -> None:
    def read_in() -> Iterator[type_utils.KeySerializedExample]:
      in_dataset = self.in_file_adapter.make_tf_data(filename=self.in_path)
      for i, row in enumerate(in_dataset):
        yield i, row.numpy()

    self.out_file_adapter.write_examples(path=self.out_path, iterator=read_in())


def _create_shard_instructions(
    num_shards: int,
    in_filename_template: naming.ShardedFileTemplate,
    in_file_adapter: Type[file_adapters.FileAdapter],
    out_filename_template: naming.ShardedFileTemplate,
    out_file_adapter: Type[file_adapters.FileAdapter],
) -> list[ShardInstruction]:
  """Returns shard instructions for the given split."""
  if num_shards <= 0:
    raise ValueError('num_shards must be positive.')
  instructions = []
  for shard_index in range(num_shards):
    in_file_path = in_filename_template.sharded_filepath(
        shard_index=shard_index, num_shards=num_shards
    )
    out_file_path = out_filename_template.sharded_filepath(
        shard_index=shard_index, num_shards=num_shards
    )
    instructions.append(
        ShardInstruction(
            in_path=in_file_path,
            in_file_adapter=in_file_adapter,
            out_path=out_file_path,
            out_file_adapter=out_file_adapter,
        )
    )
  return instructions


def _shard_instructions_for_split(
    split_info: splits_lib.SplitInfo,
    out_file_format: file_adapters.FileFormat,
    out_path: epath.Path,
    in_file_adapter: Type[file_adapters.FileAdapter],
    out_file_adapter: Type[file_adapters.FileAdapter],
) -> list[ShardInstruction]:
  """Returns shard instructions for the given split."""
  if split_info.filename_template is None:
    raise ValueError(f'Filename template for split {split_info.name} is empty.')

  in_filename_template = split_info.filename_template
  out_filename_template = in_filename_template.replace(
      data_dir=out_path, filetype_suffix=out_file_format.value
  )
  num_shards = len(split_info.shard_lengths)
  return _create_shard_instructions(
      num_shards=num_shards,
      in_filename_template=in_filename_template,
      in_file_adapter=in_file_adapter,
      out_filename_template=out_filename_template,
      out_file_adapter=out_file_adapter,
  )


def get_all_shard_instructions(
    info: dataset_info.DatasetInfo,
    out_file_format: file_adapters.FileFormat,
    out_path: epath.Path,
    in_file_adapter: Type[file_adapters.FileAdapter],
    out_file_adapter: Type[file_adapters.FileAdapter],
) -> list[ShardInstruction]:
  """Returns all shard instructions for the given dataset info."""
  shard_instructions = []
  for split_info in info.splits.values():
    shard_instructions.extend(
        _shard_instructions_for_split(
            split_info=split_info,
            out_file_format=out_file_format,
            out_path=out_path,
            in_file_adapter=in_file_adapter,
            out_file_adapter=out_file_adapter,
        )
    )
  return shard_instructions


def convert_metadata(
    info: dataset_info.DatasetInfo,
    out_file_format: file_adapters.FileFormat,
    out_path: epath.Path,
) -> None:
  info.as_proto.file_format = out_file_format.value
  info.write_to_directory(out_path)