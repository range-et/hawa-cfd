import warnings
from copy import copy

import torch

from ... import Flow, Collision, TorchStencil
from .. import D3Q27, D2Q9, QuadraticEquilibrium, QuadraticEquilibriumLessMemory

__all__ = ['KBCCollision3D', 'KBCCollision2D', 'KBCCollision']

# Hawa: double-float ("hi + lo") arithmetic for devices without FP64 (MPS).
# Each value is an unevaluated FP32 pair. TwoSum (Knuth) and Dekker's TwoProduct
# are exact under IEEE round-to-nearest; they need separately rounded torch ops.
_FP32_SPLITTER = 4097.0  # 2**12 + 1 splits a 24-bit significand into halves.


def _two_sum(a, b):
    s = a + b
    v = s - a
    return s, (a - (s - v)) + (b - v)


def _split(a):
    c = _FP32_SPLITTER * a
    high = c - (c - a)
    return high, a - high


def _two_product(a, b):
    p = a * b
    a_high, a_low = _split(a)
    b_high, b_low = _split(b)
    return p, ((a_high * b_high - p) + a_high * b_low + a_low * b_high) + a_low * b_low


def _df_add(a, b):
    s, e = _two_sum(a[0], b[0])
    return _two_sum(s, e + a[1] + b[1])


def _df_sub(a, b):
    return _df_add(a, (-b[0], -b[1]))


def _df_mul(a, b):
    p, e = _two_product(a[0], b[0])
    return _two_sum(p, e + a[0] * b[1] + a[1] * b[0])


def _df_div(a, b):
    quotient = a[0] / b[0]
    remainder = _df_sub(a, _df_mul((quotient, torch.zeros_like(quotient)), b))
    return _two_sum(quotient, remainder[0] / b[0])


def _df_sum(x, low=None):
    """Sum FP32 pairs (x, low) over dimension 0, retaining every addition error."""
    low = torch.zeros_like(x[0]) if low is None else low.sum(0)
    while x.shape[0] > 1:
        half = x.shape[0] // 2
        s, e = _two_sum(x[:half], x[half:2 * half])
        low = low + e.sum(0)
        x = torch.cat([s, x[2 * half:]])
    return _two_sum(x[0], low)


def _df_constant(value, like):
    """Represent a Python (FP64) constant as broadcastable hi/lo scalars."""
    high = float(torch.tensor(value, dtype=like.dtype))
    return tuple(torch.tensor(v, dtype=like.dtype, device=like.device) for v in (high, value - high))


def _moment_axis(x, axis, inverse):
    """Exact 1D raw-moment transform for velocities (-1, 0, 1) along `axis`."""
    a, b, c = ((x[0].select(axis, i), x[1].select(axis, i)) for i in range(3))
    if inverse:  # a, b, c are moments of order 0, 1 and 2.
        half = lambda v: (0.5 * v[0], 0.5 * v[1])
        parts = (half(_df_sub(c, b)), _df_sub(a, c), half(_df_add(c, b)))
    else:  # a, b, c are populations with velocity -1, 0 and 1.
        parts = (_df_add(_df_add(a, b), c), _df_sub(c, a), _df_add(c, a))
    return tuple(torch.stack([part[k] for part in parts], axis) for k in range(2))


class KBCCollision(Collision):
    """
    Entropic multi-relaxation time-relaxation time model according to Karlin
    et al.
    """

    def __init__(self, tau: float = None):
        self.tau = tau
        self.beta = None
        self.M = None
        self._compute_context = None
        self._compute_stencil = None

    def kbc_moment_transform(self, f):
        pass

    def kbc_moment_transform_3d(self, f):
        """Transforms the f into the KBC moment representation"""
        m = torch.einsum('abcq,qmno', self.M, f)
        rho = m[0, 0, 0]
        m = m / rho
        m[0, 0, 0] = rho
        return m

    def kbc_moment_transform_2d(self, f):
        """Transforms the f into the KBC moment representation"""
        m = torch.einsum('abq,qmn', self.M, f)
        rho = m[0, 0]
        m = m / rho
        m[0, 0] = rho
        return m

    def compute_s_seq_from_m(self, f, m):
        pass

    def compute_s_seq_from_m_3d(self, f, m):
        s = torch.zeros_like(f)

        T = m[2, 0, 0] + m[0, 2, 0] + m[0, 0, 2]
        N_xz = m[2, 0, 0] - m[0, 0, 2]
        N_yz = m[0, 2, 0] - m[0, 0, 2]
        Pi_xy = m[1, 1, 0]
        Pi_xz = m[1, 0, 1]
        Pi_yz = m[0, 1, 1]

        s[0] = m[0, 0, 0] * -T
        s[1] = 1. / 6. * m[0, 0, 0] * (2 * N_xz - N_yz + T)
        s[2] = s[1]
        s[3] = 1. / 6. * m[0, 0, 0] * (2 * N_yz - N_xz + T)
        s[4] = s[3]
        s[5] = 1. / 6. * m[0, 0, 0] * (-N_xz - N_yz + T)
        s[6] = s[5]
        s[7] = 1. / 4 * m[0, 0, 0] * Pi_yz
        s[8] = s[7]
        s[9] = - 1. / 4 * m[0, 0, 0] * Pi_yz
        s[10] = s[9]
        s[11] = 1. / 4 * m[0, 0, 0] * Pi_xz
        s[12] = s[11]
        s[13] = -1. / 4 * m[0, 0, 0] * Pi_xz
        s[14] = s[13]
        s[15] = 1. / 4 * m[0, 0, 0] * Pi_xy
        s[16] = s[15]
        s[17] = -1. / 4 * m[0, 0, 0] * Pi_xy
        s[18] = s[17]

        return s

    def compute_s_seq_from_m_2d(self, f, m):
        s = torch.zeros_like(f)

        T = m[2, 0] + m[0, 2]
        N = m[2, 0] - m[0, 2]

        Pi_xy = m[1, 1]

        s[0] = m[0, 0] * -T
        s[1] = 1. / 2. * m[0, 0] * (0.5 * (T + N))
        s[2] = 1. / 2. * m[0, 0] * (0.5 * (T - N))
        s[3] = 1. / 2. * m[0, 0] * (0.5 * (T + N))
        s[4] = 1. / 2. * m[0, 0] * (0.5 * (T - N))
        s[5] = 1. / 4. * m[0, 0] * Pi_xy
        s[6] = -s[5]
        s[7] = 1. / 4 * m[0, 0] * Pi_xy
        s[8] = -s[7]

        return s

    def __call__(self, flow: 'Flow') -> torch.Tensor:
        # KBC subtracts nearly equal equilibrium/shear moments before dividing
        # by a quadratic higher-order residual. FP32 rounding in those moments
        # can therefore cause a large stabilizer error, not just an output ulp.
        # Use wider intermediates where the device supports them, while keeping
        # storage, streaming and the returned populations in the requested dtype.
        # MPS has no FP64 and never falls back to CPU: it uses FP32 hi/lo pairs.
        storage_dtype = flow.f.dtype
        epsilon = torch.finfo(storage_dtype).eps
        if storage_dtype == torch.float32 and flow.f.device.type not in ('cpu', 'cuda') \
                and type(flow.equilibrium) in (QuadraticEquilibrium, QuadraticEquilibriumLessMemory):
            # Without FP64 (MPS), emulate the wider intermediates in FP32 pairs.
            return self._collide_compensated(flow, epsilon)
        if storage_dtype == torch.float32 and flow.f.device.type in ('cpu', 'cuda'):
            if self._compute_context is None:
                self._compute_context = copy(flow.context)
                self._compute_context.dtype = torch.float64
                self._compute_stencil = TorchStencil(flow.stencil, self._compute_context)
            working = copy(flow)
            working.context = self._compute_context
            working.torch_stencil = self._compute_stencil
            working.f = flow.f.to(torch.float64)
            return self._collide(working, epsilon).to(storage_dtype)
        return self._collide(flow, epsilon)

    def _initialize(self, flow: 'Flow'):
        if self.M is None:
            self.tau = flow.units.relaxation_parameter_lu
            self.beta = 1. / (2 * self.tau)
            if flow.stencil.d == 3:
                assert isinstance(flow.stencil, D3Q27), \
                    "KBC Collision is only implemented for D3Q27!"
                self.compute_s_seq_from_m = self.compute_s_seq_from_m_3d
                self.kbc_moment_transform = self.kbc_moment_transform_3d
                # Build a matrix that contains the indices
                self.M = flow.context.zero_tensor([3, 3, 3, 27])
                torch_stencil = TorchStencil(D3Q27(), flow.context)
                for i in range(3):
                    for j in range(3):
                        for k in range(3):
                            self.M[i, j, k] = (torch_stencil.e[:, 0] ** i *
                                               torch_stencil.e[:, 1] ** j *
                                               torch_stencil.e[:, 2] ** k)
            elif flow.stencil.d == 2:
                assert isinstance(flow.stencil, D2Q9), \
                    "KBC Collision is only implemented for D2Q9!"
                self.compute_s_seq_from_m = self.compute_s_seq_from_m_2d
                self.kbc_moment_transform = self.kbc_moment_transform_2d
                # Build a matrix that contains the indices
                self.M = flow.context.zero_tensor([3, 3, 9])
                torch_stencil = TorchStencil(D2Q9(), flow.context)
                for i in range(3):
                    for j in range(3):
                        self.M[i, j] = (torch_stencil.e[:, 0] ** i
                                        * torch_stencil.e[:, 1] ** j)
            else:
                raise NotImplementedError("KBC Collision is only implemented "
                                          "for 2d and 3d!")

    def _collide_compensated(self, flow: 'Flow', epsilon: float) -> torch.Tensor:
        """FP32 KBC collision with double-float intermediates (Hawa, HAWA-001).

        The same KBC decomposition as `_collide`, evaluated without FP64. Plain
        FP32 rounds the equilibrium at ulp(feq), which is large relative to the
        higher-order residual delta_h, and subtracts nearly equal shear moments.
        The stabilizer then crosses the negative-value reset depending on
        reduction order. Here rho, j, the quadratic equilibrium and the residual
        f - feq are FP32 pairs. Exact raw-moment transforms split the residual
        into its second-order (delta_s) and third/fourth-order (delta_h) moments;
        the conserved moments of the residual are zero in exact arithmetic and
        are not reconstructed. The update is rounded to FP32 once. Requires
        Lettuce's quadratic equilibrium with u = j / rho and D2Q9 or D3Q27.
        """
        self._initialize(flow)
        f = flow.f
        d, q, spatial = flow.stencil.d, flow.stencil.q, f.shape[1:]
        zero = torch.zeros_like(f)
        e = flow.torch_stencil.e.to(f.dtype).view(q, d, *([1] * d))
        moments = _df_sum(torch.cat([f[:, None], e * f[:, None]], dim=1))
        rho = (moments[0][0].expand_as(f), moments[1][0].expand_as(f))
        e_dot_j = (zero, zero)
        j_squared = (zero[0], zero[0])
        for axis in range(d):
            j_axis = (moments[0][1 + axis], moments[1][1 + axis])
            e_dot_j = _df_add(e_dot_j, (e[:, axis] * j_axis[0], e[:, axis] * j_axis[1]))
            j_squared = _df_add(j_squared, _df_mul(j_axis, j_axis))
        # feq = w (rho + e.j / cs^2 + ((e.j)^2 / (2 cs^4) - j.j / (2 cs^2)) / rho)
        inverse_cs2 = 1. / flow.stencil.cs ** 2
        quadratic = _df_sub(_df_mul(_df_constant(0.5 * inverse_cs2 ** 2, f), _df_mul(e_dot_j, e_dot_j)),
                            _df_mul(_df_constant(0.5 * inverse_cs2, f), j_squared))
        bracket = _df_add(_df_add(rho, _df_mul(_df_constant(inverse_cs2, f), e_dot_j)),
                          _df_div(quadratic, rho))
        weights = torch.tensor(flow.stencil.w, dtype=torch.float64)
        weight_high = weights.to(f.dtype)
        weight_low = (weights - weight_high.to(torch.float64)).to(f.dtype)
        shape = (q,) + (1,) * d
        weight = (weight_high.to(f.device).view(shape), weight_low.to(f.device).view(shape))
        feq = _df_mul(weight, bracket)
        fneq = _df_sub((f, zero), feq)

        # Arrange populations on a 3^d velocity grid for separable transforms.
        grid = [sum((int(c) + 1) * 3 ** (d - 1 - a) for a, c in enumerate(v)) for v in flow.stencil.e]
        population_at = [0] * q
        for population, position in enumerate(grid):
            population_at[position] = population
        m = tuple(part[population_at].reshape(*([3] * d), *spatial) for part in fneq)
        for axis in range(d):
            m = _moment_axis(m, axis, inverse=False)
        order = sum(torch.arange(3, device=f.device).view(*([1] * a), 3, *([1] * (d - 1 - a)))
                    for a in range(d)).view(*([3] * d), *([1] * len(spatial)))

        def reconstruct(selected):
            r = tuple(torch.where(selected, part, torch.zeros_like(part)) for part in m)
            for axis in range(d):
                r = _moment_axis(r, axis, inverse=True)
            return tuple(part.reshape(q, *spatial)[grid] for part in r)

        delta_s = reconstruct(order == 2)
        delta_h = reconstruct(order >= 3)
        # The stabilizer must also be wide: 1/beta - (2 - 1/beta) sum_s/sum_h
        # nearly cancels when tau is close to 1/2.
        sum_s = _df_sum(*_df_div(_df_mul(delta_s, delta_h), feq))
        sum_h = _df_sum(*_df_div(_df_mul(delta_h, delta_h), feq))
        # Same storage-precision guard and inherited reset as `_collide`.
        near_zero = sum_h[0] <= (flow.stencil.q * epsilon) ** 2 * flow.rho()[0]
        denominator = (torch.where(near_zero, torch.ones_like(sum_h[0]), sum_h[0]),
                       torch.where(near_zero, torch.zeros_like(sum_h[1]), sum_h[1]))
        gamma_stab = _df_sub(_df_constant(1. / self.beta, f),
                             _df_mul(_df_constant(2 - 1. / self.beta, f), _df_div(sum_s, denominator)))
        reset = near_zero | ~torch.isfinite(gamma_stab[0]) | (gamma_stab[0] < 1E-15)
        gamma_stab = (torch.where(reset, torch.full_like(gamma_stab[0], 2.0), gamma_stab[0]),
                      torch.where(reset, torch.zeros_like(gamma_stab[1]), gamma_stab[1]))
        correction = _df_add(_df_mul(_df_constant(2 * self.beta, f), delta_s),
                             _df_mul(_df_constant(self.beta, f), _df_mul(gamma_stab, delta_h)))
        return _df_sub((f, zero), correction)[0]

    def _collide(self, flow: 'Flow', epsilon: float) -> torch.Tensor:
        self._initialize(flow)
        # the deletes are not part of the algorithm, they just keep the memory
        # usage lower
        feq = flow.equilibrium(flow)
        # k = torch.zeros_like(f)

        m = self.kbc_moment_transform(flow.f)
        delta_s = self.compute_s_seq_from_m(flow.f, m)

        # k[1] = m[0, 0, 0] / 6. * (3. * m[1, 0, 0])
        # k[0] = m[0, 0, 0]
        # k[2] = -k[1]
        # k[3] = m[0, 0, 0] / 6. * (3. * m[0, 1, 0])
        # k[4] = -k[3]
        # k[5] = m[0, 0, 0] / 6. * (3. * m[0, 0, 1])
        # k[6] = -k[5]

        m = self.kbc_moment_transform(feq)
        delta_s -= self.compute_s_seq_from_m(flow.f, m)
        del m

        delta_h = flow.f - feq - delta_s
        sum_s = flow.rho(delta_s * delta_h / feq)
        sum_h = flow.rho(delta_h * delta_h / feq)
        del feq

        # A pure shear perturbation has zero higher-order entropy. In FP32,
        # dividing by its roundoff residue produces an unbounded stabilizer.
        # The uncertainty comes from stored populations, even when intermediates
        # are wider. Preserve the existing storage-precision degeneracy guard.
        near_zero = sum_h <= (flow.stencil.q * epsilon) ** 2 * flow.rho()
        denominator = torch.where(near_zero, torch.ones_like(sum_h), sum_h)
        gamma_stab = 1. / self.beta - (2 - 1. / self.beta) * sum_s / denominator
        gamma_stab = torch.where(near_zero | ~torch.isfinite(gamma_stab),
                                 torch.full_like(gamma_stab, 2.0), gamma_stab)
        gamma_stab[gamma_stab < 1E-15] = 2.0
        # Detect NaN
        gamma_stab[torch.isnan(gamma_stab)] = 2.0
        f = flow.f - self.beta * (2 * delta_s + gamma_stab * delta_h)

        return f

    def native_available(self) -> bool:
        return False

    def native_generator(self, index: int) -> 'NativeCollision':
        pass


class KBCCollision2D(KBCCollision):
    def __init__(self, tau: float = None):
        warnings.warn("KBCCollision2D is is deprecated! Use KBCCollision "
                      "instead!")
        super().__init__()


class KBCCollision3D(KBCCollision):
    def __init__(self, tau: float = None):
        warnings.warn("KBCCollision2D is is deprecated! Use KBCCollision "
                      "instead!")
        super().__init__()
