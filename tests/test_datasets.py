from __future__ import division, print_function, absolute_import

from nnmnkwii.datasets import FileSourceDataset, PaddedFileSourceDataset
from nnmnkwii.datasets import MemoryCacheFramewiseDataset
from nnmnkwii.util import example_file_data_sources_for_acoustic_model
from nnmnkwii.util import example_file_data_sources_for_duration_model

import numpy as np
from nose.tools import raises
from os.path import join, dirname

DATA_DIR = join(dirname(__file__), "data")


def _get_small_datasets(padded=False, duration=False):
    if duration:
        X, Y = example_file_data_sources_for_duration_model()
    else:
        X, Y = example_file_data_sources_for_acoustic_model()
    if padded:
        X = PaddedFileSourceDataset(X, padded_length=1000)
        Y = PaddedFileSourceDataset(Y, padded_length=1000)
    else:
        X = FileSourceDataset(X)
        Y = FileSourceDataset(Y)
    return X, Y


def test_duration_sources():
    X, Y = _get_small_datasets(padded=False, duration=True)
    for idx, (x, y) in enumerate(zip(X, Y)):
        print(idx, x.shape, y.shape)


def test_slice():
    X, _ = _get_small_datasets(padded=False)
    x = X[:2]
    assert isinstance(x, list)
    assert len(x) == 2

    X, _ = _get_small_datasets(padded=True)
    x = X[:2]
    assert isinstance(x, np.ndarray)
    assert len(x.shape) == 3 and x.shape[0] == 2


def test_variable_length_sequence_wise_iteration():
    X, Y = _get_small_datasets(padded=False)
    for idx, (x, y) in enumerate(zip(X, Y)):
        print(idx, x.shape, y.shape)


def test_fixed_length_sequence_wise_iteration():
    X, Y = _get_small_datasets(padded=True)

    Tx = X[0].shape[0]
    Ty = Y[0].shape[0]
    assert Tx == Ty
    for idx, (x, y) in enumerate(zip(X, Y)):
        print(idx, x.shape, y.shape)
        assert x.shape[0] == Tx
        assert y.shape[0] == Ty


def test_frame_wise_iteration():
    X, Y = _get_small_datasets(padded=False)

    lengths = np.array([len(x) for x in X], dtype=np.int)
    num_utterances = len(lengths)

    # With sufficient cache size
    X = MemoryCacheFramewiseDataset(X, lengths, cache_size=len(X))
    Y = MemoryCacheFramewiseDataset(Y, lengths, cache_size=len(Y))

    assert np.sum(lengths) == len(X)
    assert len(X) == len(Y)

    Dx = X[0].shape[-1]
    Dy = Y[0].shape[-1]
    for idx, (x, y) in enumerate(zip(X, Y)):
        assert x.shape[-1] == Dx
        assert y.shape[-1] == Dy

    assert len(X.cached_utterances) == num_utterances
    assert len(Y.cached_utterances) == num_utterances

    # Should support slice indexing
    for idx, (x, y) in enumerate(zip(X[:2], Y[:2])):
        pass


def test_sequence_wise_torch_data_loader():
    import torch
    from torch.utils import data as data_utils

    X, Y = _get_small_datasets(padded=False)

    class TorchDataset(data_utils.Dataset):
        def __init__(self, X, Y):
            self.X = X
            self.Y = Y

        def __getitem__(self, idx):
            return torch.from_numpy(self.X[idx]), torch.from_numpy(self.Y[idx])

        def __len__(self):
            return len(self.X)

    def __test(X, Y, batch_size):
        dataset = TorchDataset(X, Y)
        loader = data_utils.DataLoader(
            dataset, batch_size=batch_size, num_workers=1, shuffle=True)
        for idx, (x, y) in enumerate(loader):
            assert len(x.shape) == len(y.shape)
            assert len(x.shape) == 3
            print(idx, x.shape, y.shape)

    # Test with batch_size = 1
    yield __test, X, Y, 1
    # Since we have variable length frames, batch size larger than 1 causes
    # runtime error.
    yield raises(RuntimeError)(__test), X, Y, 2

    # For padded dataset, which can be reprensented by (N, T^max, D), batchsize
    # can be any number.
    X, Y = _get_small_datasets(padded=True)
    yield __test, X, Y, 1
    yield __test, X, Y, 2


def test_frame_wise_torch_data_loader():
    import torch
    from torch.utils import data as data_utils

    X, Y = _get_small_datasets(padded=False)

    # Since torch's Dataset (and Chainer, and maybe others) assumes dataset has
    # fixed size length, i.e., implements `__len__` method, we need to know
    # number of frames for each utterance.
    # Sum of the number of frames is the dataset size for frame-wise iteration.
    lengths = np.array([len(x) for x in X], dtype=np.int)

    # For the above reason, we need to explicitly give the number of frames.
    X = MemoryCacheFramewiseDataset(X, lengths, cache_size=len(X))
    Y = MemoryCacheFramewiseDataset(Y, lengths, cache_size=len(Y))

    class TorchDataset(data_utils.Dataset):
        def __init__(self, X, Y):
            self.X = X
            self.Y = Y

        def __getitem__(self, idx):
            return torch.from_numpy(self.X[idx]), torch.from_numpy(self.Y[idx])

        def __len__(self):
            return len(self.X)

    def __test(X, Y, batch_size):
        dataset = TorchDataset(X, Y)
        loader = data_utils.DataLoader(
            dataset, batch_size=batch_size, num_workers=1, shuffle=True)
        for idx, (x, y) in enumerate(loader):
            assert len(x.shape) == 2
            assert len(y.shape) == 2

    yield __test, X, Y, 128
    yield __test, X, Y, 256
