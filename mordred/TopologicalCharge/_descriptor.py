from .._base import Descriptor
from .._common import AdjacencyMatrix, DistanceMatrix
from six import integer_types

import numpy as np


class ChargeTermMatrix(Descriptor):
    explicit_hydrogens = False

    @property
    def dependencies(self):
        return dict(
            A=AdjacencyMatrix.make_key(
                self.explicit_hydrogens,
                False,
            ),
            D=DistanceMatrix.make_key(
                self.explicit_hydrogens,
                False,
                False,
            ),
        )

    @property
    def descriptor_key(self):
        return self.make_key()

    def calculate(self, mol, A, D):
        D2 = D.copy()
        D2[D2 != 0] **= -2
        np.fill_diagonal(D2, 0)

        M = A.dot(D2)
        return M - M.T


class TopologicalCharge(Descriptor):
    explicit_hydrogens = False

    @classmethod
    def preset(cls):
        for v in ((t, o) for t in ('raw', 'mean') for o in range(1, 11)):
            yield v

        yield 'global', 10

    @property
    def dependencies(self):
        return dict(
            CT=ChargeTermMatrix.make_key(),
            D=DistanceMatrix.make_key(
                self.explicit_hydrogens,
                False,
                False,
            )
        )

    @property
    def descriptor_key(self):
        return self.make_key(self.type, self.order)

    @property
    def descriptor_name(self):
        if self.type == 'global':
            return 'JGT{}'.format(self.order)
        elif self.type == 'mean':
            return 'JGI{}'.format(self.order)
        else:
            return 'GGI{}'.format(self.order)

    def __init__(self, type='global', order=10):
        assert type in ['global', 'mean', 'raw']
        assert type == 'global' or isinstance(order, integer_types)

        self.type = type
        self.order = order

    def calculate(self, mol, CT, D):
        D = D * np.tri(*D.shape)
        D[D == 0] = np.inf

        f = D <= self.order if self.type == 'global' else D == self.order

        CT = CT[f]

        if self.type == 'raw':
            return np.abs(CT).sum()

        # create frequency vector
        Df = D[f]
        C = Df.copy()
        for i in np.unique(Df):
            C[Df == i] = len(Df[Df == i])

        return np.abs(CT / C).sum()

_descriptors = [TopologicalCharge]
__all__ = [d.__name__ for d in _descriptors]
