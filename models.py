
import torch
import torch.nn as nn
from torch.autograd import Variable
from utils import to_cuda, init_weights


class EqualizedConv2D(nn.Module):

    def __init__(self, in_dim, out_dim, kernel_size, padding):
        super(EqualizedConv2D, self).__init__()

        self.conv = nn.Conv2d(in_dim, out_dim, kernel_size, padding=padding)
        self.conv.apply(init_weights)
        self.conv.bias.data = self.conv.bias.data.zero_() 
        self.conv = nn.utils.weight_norm(self.conv)
    
    def forward(self, x):
        return self.conv(x)

def conv_bn_relu(in_dim, out_dim, kernel_size, padding=0):
    return nn.Sequential(
        EqualizedConv2D(in_dim, out_dim, kernel_size, padding),
        PixelwiseNormalization(),
        nn.LeakyReLU()
    )


def get_transition_value(x_old, x_new, transition_variable):
    return (1-transition_variable) * x_old + transition_variable*x_new

class PixelwiseNormalization(nn.Module):

    def __init__(self):
        super(PixelwiseNormalization, self).__init__()

    def forward(self, x):
        factor = (x**2).mean(dim=1, keepdim=True)**0.5
        return x / factor

class UpSamplingBlock(nn.Module):
    def __init__(self):
        super(UpSamplingBlock, self).__init__()
    def forward(self, x):
        return nn.functional.interpolate(x, scale_factor=2)

class Generator(nn.Module):

    def __init__(self, noise_dim):
        super(Generator, self).__init__()
        # Transition blockss
        self.to_rgb_new = EqualizedConv2D(128, 1, 1, 0)
        self.to_rgb_old = EqualizedConv2D(128, 1, 1, 0)
        self.new_block = nn.Sequential(
        )
        self.core_model = nn.Sequential(
            conv_bn_relu(noise_dim, 128, 3, 1),            
        )
        self.first_block = nn.Sequential(
            nn.Linear(noise_dim, noise_dim*4*4)
        )
    
    def extend(self, output_dim):
        # Find input shape
        input_dim = self.to_rgb_new.conv.weight.shape[1]
        self.core_model = nn.Sequential(
            self.core_model,
            self.new_block,
            UpSamplingBlock()
        )
        self.new_block = nn.Sequential(
            conv_bn_relu(input_dim, output_dim, 3, 1),
            conv_bn_relu(output_dim, output_dim, 3, 1)
        )
        self.new_block = to_cuda(self.new_block) 
        self.to_rgb_old = self.to_rgb_new
        self.to_rgb_new = EqualizedConv2D(output_dim, 1, 1,0)
        self.to_rgb_new = to_cuda(self.to_rgb_new)


    # x: Bx1x1x512
    def forward(self, x, transition_variable=1):
        x = x.view((x.shape[0], -1))
        x = self.first_block(x)
        x = x.view(x.shape[0], -1, 4, 4)
        
        x = self.core_model(x)
        x_old = self.to_rgb_old(x)
        x_new = self.new_block(x)
        x_new = self.to_rgb_new(x_new)        
        x = get_transition_value(x_old, x_new, transition_variable)
        return x


def conv_module(dim_in, dim_out, kernel_size, padding, image_width):
    return nn.Sequential(
        EqualizedConv2D(dim_in, dim_out, kernel_size, padding),
        nn.LeakyReLU()
    )

class Discriminator(nn.Module):

    def __init__(self, in_channels, imsize):
        super(Discriminator, self).__init__()
        self.image_channels = in_channels
        self.current_input_imsize = 4
        self.from_rgb_new = conv_module(in_channels,128,1,0,self.current_input_imsize)

        self.from_rgb_old = conv_module(in_channels,128,1,0,self.current_input_imsize)
        self.new_block = nn.Sequential()
        self.core_model = nn.Sequential(
            conv_module(128, 128, 3, 1, imsize),
            conv_module(128, 128, 4, 0, 1),            
        )
        self.output_layer = nn.Linear(128, 1)

        
    def extend(self, input_dim):
        
        self.current_input_imsize *= 2
        output_dim = list(self.from_rgb_new.parameters())[1].shape[0]
        self.core_model = nn.Sequential(
            self.new_block,
            self.core_model
        )
        self.from_rgb_old = nn.Sequential(
            nn.AvgPool2d([2,2]),
            self.from_rgb_new
        )
        self.from_rgb_new = conv_module(self.image_channels, input_dim, 1, 0,self.current_input_imsize)
        self.from_rgb_new = to_cuda(self.from_rgb_new)
        self.new_block = nn.Sequential(
            conv_module(input_dim, input_dim, 3, 1, self.current_input_imsize),
            conv_module(input_dim, output_dim, 3, 1, self.current_input_imsize),
            nn.AvgPool2d([2, 2])
        )
        self.new_block = to_cuda(self.new_block)



    # x: Bx1x1x512
    def forward(self, x, transition_variable=1):
        x_old = self.from_rgb_old(x)
        x_new = self.from_rgb_new(x)
        x_new = self.new_block(x_new)
        x = get_transition_value(x_old, x_new, transition_variable)
        x = self.core_model(x)
        x = x.view(-1, 128)
        x = self.output_layer(x)
        return x


if __name__ == "__main__":

    # Test that logits is the same

    # real data
    z = to_cuda(torch.zeros((64, 128, 1,1)))
    d = Discriminator(1, 4).cuda()
    g = Generator(128).cuda()
    data = g(z, 1)
    logits = d(data, 1)


    print(logits)

    d.extend(32)
    g.extend(32)

    data = g(z, 0)
    lg = d(data, 0)
    print(lg)

