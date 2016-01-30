import networkx

import numpy as np

from . import _matrix_attributes as ma
from ._base import Descriptor


class LongestSimplePath(object):
    __slots__ = (
        'G', 'N', 'neighbors',
        'start', 'result', 'visited', 'distance',
    )

    def __init__(self, G, weight=None):
        self.G = G
        self.N = G.number_of_nodes()
        self.neighbors = {
            n: [(v, d.get(weight, 1.0)) for v, d in G[n].items()]
            for n in G.nodes_iter()
        }

    def _start(self, s):
        self.start = s
        self.result = {n: 0 for n in self.G.nodes_iter()}
        self.visited = set()
        self.distance = 0.0
        self._search(s)
        return self.result

    def _search(self, u):
        self.visited.add(u)
        for v, w in self.neighbors[u]:
            if v in self.visited:
                continue

            self.visited.add(v)
            self.distance += w

            d = self.distance
            if d > self.result[v]:
                self.result[v] = d

            if v != self.start:
                self._search(v)

            self.visited.remove(v)
            self.distance -= w

    def __call__(self):
        return {(min(s, g), max(s, g)): w
                for s in self.G.nodes_iter()
                for g, w in self._start(s).items()}


class CalcDetour(object):
    __slots__ = ('N', 'Q', 'nodes', 'C')

    def __init__(self, G, weight='weight'):
        self.N = G.number_of_nodes()
        self.Q = []
        for bcc in networkx.biconnected_component_subgraphs(G, False):
            lsp = LongestSimplePath(bcc, weight)()
            nodes = set()
            for a, b in lsp:
                nodes.add(a)
                nodes.add(b)
            self.Q.append((nodes, lsp))

    def merge(self):
        for i in range(1, len(self.Q) + 1):
            ns, lsp = self.Q[-i]
            common = ns & self.nodes
            if len(common) == 0:
                continue
            elif len(common) > 1:
                raise ValueError('bug: multiple common nodes.')

            common = common.pop()
            self.Q.pop(-i)
            for n in ns:
                self.nodes.add(n)
            break

        def calc_weight(i, j):
            ij = (i, j)
            if ij in self.C:
                return self.C[ij]
            elif ij in lsp:
                return lsp[ij]
            elif i == j == common:
                return max(lsp[ij], self.C[ij])

            ic = (min(i, common), max(i, common))
            jc = (min(j, common), max(j, common))

            if ic in self.C and jc in lsp:
                return self.C[ic] + lsp[jc]
            elif jc in self.C and ic in lsp:
                return self.C[jc] + lsp[ic]
            else:
                raise ValueError('bug: unknown weight')

        self.C = {(i, j): calc_weight(i, j)
                  for i in self.nodes
                  for j in self.nodes
                  if i <= j}

    def __call__(self):
        if self.N == 1:
            return np.array([[0]])

        self.nodes, self.C = self.Q.pop()

        while self.Q:
            self.merge()

        result = np.empty((self.N, self.N))
        for i, j in ((i, j) for i in range(self.N) for j in range(i, self.N)):
            result[i, j] = self.C[(i, j)]
            result[j, i] = self.C[(i, j)]

        return result


class DetourMatrixBase(Descriptor):
    explicit_hydrogens = False
    require_connected = True


class DetourMatrixCache(DetourMatrixBase):
    __slots__ = ()

    def __reduce_ex__(self, version):
        return self.__class__, ()

    def calculate(self, mol):
        G = networkx.Graph()
        G.add_nodes_from(a.GetIdx() for a in mol.GetAtoms())
        G.add_edges_from(
            (b.GetBeginAtomIdx(), b.GetEndAtomIdx())
            for b in mol.GetBonds()
        )

        return CalcDetour(G)()


class DetourMatrix(DetourMatrixBase):
    r"""detour matrix descriptor.

    :type type: str
    :param type: :ref:`matrix_aggregating_methods`
    """

    @classmethod
    def preset(cls):
        return map(cls, ma.methods)

    def __str__(self):
        return '{}_Dt'.format(self._type.__name__)

    __slots__ = ('_type',)

    def __reduce_ex__(self, version):
        return self.__class__, (self._type,)

    def __init__(self, type='SpMax'):
        self._type = ma.get_method(type)

    def dependencies(self):
        return dict(
            result=self._type(
                DetourMatrixCache(),
                self.explicit_hydrogens,
                self.gasteiger_charges,
                self.kekulize,
            )
        )

    def calculate(self, mol, result):
        return result

    rtype = float


class DetourIndex(DetourMatrixBase):
    r"""detour index descriptor.

    .. math::

        I_{\rm D} = \frac{1}{A} \sum^A_{i=1} \sum^A_{j=1} {\boldsymbol D}_{ij}

    where
    :math:`D` is detour matrix,
    :math:`A` is number of atoms.
    """

    __slots__ = ()

    def __reduce_ex__(self, version):
        return self.__class__, ()

    @classmethod
    def preset(cls):
        yield cls()

    explicit_hydrogens = False

    def __str__(self):
        return 'DetourIndex'

    def dependencies(self):
        return dict(
            D=DetourMatrixCache()
        )

    def calculate(self, mol, D):
        return int(0.5 * D.sum())

    rtype = int