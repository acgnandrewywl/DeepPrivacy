import numpy as np
import torch
import math
from deep_privacy.data_tools import data_utils


def image_to_numpy(images, to_uint8=False, denormalize=False):
    single_image = False
    if len(images.shape) == 3:
        single_image = True
        images = images[None]
    if denormalize:
        images = data_utils.denormalize_img(images)
    images = images.detach().cpu().numpy()
    r, g, b = images[:, 0], images[:, 1], images[:, 2]
    images = np.stack((r, g, b), axis=3)
    if to_uint8:
        images = (images*255).astype(np.uint8)
    if single_image:
        return images[0]
    return images


def image_to_torch(image, cuda=True, normalize_img=False):
    if image.dtype == np.uint8:
        image = image.astype(np.float32)
        image /= 255
    else:
        assert image.dtype == np.float32
    image = np.rollaxis(image, 2)
    image = image[None, :, :, :]
    image = torch.from_numpy(image)
    if cuda:
        image = to_cuda(image)
    assert image.min() >= 0.0 and image.max() <= 1.0
    if normalize_img:
        image = image * 2 - 1
    return image


def to_cuda(elements):
    if torch.cuda.is_available():
        if type(elements) == tuple or type(elements) == list:
            return [x.cuda() for x in elements]
        return elements.cuda()
    return elements


def isinf(tensor):
    if not isinstance(tensor, torch.Tensor):
        raise ValueError("The argument is not a tensor", str(tensor))
    return (tensor.abs() == math.inf).any()


def isnan(tensor):
    r"""Returns a new tensor with boolean elements representing if each element
    is `NaN` or not.
    Arguments:
        tensor (Tensor): A tensor to check
    Returns:
        Tensor: A ``torch.ByteTensor`` containing a 1 at each location of `NaN`
        elements.
    Example::
        >>> torch.isnan(torch.tensor([1, float('nan'), 2]))
        tensor([ 0,  1,  0], dtype=torch.uint8)
    """
    if not isinstance(tensor, torch.Tensor):
        raise ValueError("The argument is not a tensor", str(tensor))
    return (tensor != tensor).any()


def finiteCheck(parameters):
    if isinstance(parameters, torch.Tensor):
        parameters = [parameters]
    parameters = list(filter(lambda p: p.grad is not None, parameters))
    for p in parameters:
        if isinf(p.grad.data):
            return False
        if isnan(p.grad.data):
            return False
    return True
