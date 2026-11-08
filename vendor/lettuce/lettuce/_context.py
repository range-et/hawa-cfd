from typing import List, Optional, Union

import numpy as np
import torch

__all__ = ['Context']


class Context:
    def __init__(self, device: Optional[Union[torch.device, str]] = None,
                 dtype: Optional[torch.dtype] = None,
                 use_native: Optional[bool] = None):
        # Hawa: preserve CPU/CUDA tensor behavior and add explicit MPS support.
        if device is None:
            if use_native or torch.cuda.is_available():
                device = 'cuda:0'
            else:
                device = 'cpu'
        device = torch.device(device)
        if device.type not in ('cpu', 'cuda', 'mps'):
            raise ValueError(f'Unsupported device: {device}')
        if device.type == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA explicitly requested but unavailable')
        if device.type == 'mps' and not torch.backends.mps.is_available():
            raise RuntimeError('MPS explicitly requested but unavailable')
        use_native = device.type == 'cuda' if use_native is None else use_native
        if use_native and device.type != 'cuda':
            raise ValueError('Native CUDA kernels require a CUDA device')

        dtype = dtype or torch.float32  # default dtype to single
        if device.type == 'mps' and dtype == torch.float64:
            raise ValueError('MPS does not support float64; select float32 or CPU')
        assert dtype in [torch.float16, torch.float32, torch.float64], \
            (f"lettuce is designed to work with common float types "
             f"(16, 32 and 64 bit). {dtype.__name__} is not supported!")

        # store context configuration

        self.device = torch.device(device)
        self.dtype = dtype
        self.use_native = use_native

    def synchronize(self):
        """
        Use explicit sync to catch errors right away.
        Notice cost of sync, so better call only when necessary or in setup code.
        """
        if self.device.type == 'cuda':
            torch.cuda.synchronize(self.device)
        elif self.device.type == 'mps':
            torch.mps.synchronize()

    def empty_tensor(self, size: Union[List[int], torch.Size], *args,
                     dtype=None, **kwargs) -> torch.Tensor:
        return torch.empty(size, *args, **kwargs, device=self.device,
                           dtype=(dtype or self.dtype))

    def zero_tensor(self, size: Union[List[int], torch.Size], *args,
                    dtype=None, **kwargs) -> torch.Tensor:
        return torch.zeros(size, *args, **kwargs, device=self.device,
                           dtype=(dtype or self.dtype))

    def full_tensor(self, size: Union[List[int], torch.Size], value, *args,
                    dtype=None, **kwargs) -> torch.Tensor:
        return torch.full(size, value, *args, **kwargs, device=self.device,
                           dtype=(dtype or self.dtype))

    def one_tensor(self, size: Union[List[int], torch.Size], *args, dtype=None,
                   **kwargs) -> torch.Tensor:
        return torch.ones(size, *args, **kwargs, device=self.device,
                          dtype=(dtype or self.dtype))

    def convert_to_tensor(self, array, *args,
                          dtype: Optional[torch.dtype] = None, **kwargs
                          ) -> torch.Tensor:
        is_tensor = isinstance(array, torch.Tensor)
        new_dtype = dtype

        if dtype is None:
            bool_types = [bool, torch.bool, torch.uint8, np.uint8]
            if hasattr(array, 'dtype') and array.dtype in bool_types:
                new_dtype = torch.uint8
            else:
                new_dtype = self.dtype

        # Convert nested lists to NumPy array first
        if is_tensor:
            return array.to(*args, **kwargs, device=self.device, dtype=new_dtype)

        array = np.array(array)
        array = np.ascontiguousarray(array)

        tensor = torch.from_numpy(array)
        tensor = tensor.to(*args, **kwargs, device=self.device, dtype=new_dtype)

        return tensor

    @staticmethod
    def convert_to_ndarray(tensor: Union[torch.Tensor, List]) -> np.ndarray:
        if isinstance(tensor, torch.Tensor):
            return tensor.detach().cpu().numpy()
        else:
            return np.array(tensor)
