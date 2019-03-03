from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np


class sequential(object):
    def __init__(self, *args):
        self.params = {}
        self.grads = {}
        self.layers = []
        self.paramName2Indices = {}
        self.layer_names = {}

        # process the parameters layer by layer
        for layer_cnt, layer in enumerate(args):
            for n, v in layer.params.items():
                self.params[n] = v
                self.paramName2Indices[n] = layer_cnt
            for n, v in layer.grads.items():
                self.grads[n] = v
            if layer.name in self.layer_names:
                raise ValueError("Existing name {}!".format(layer.name))
            self.layer_names[layer.name] = True
            self.layers.append(layer)

    def assign(self, name, val):
        # load the given values to the layer by name
        layer_cnt = self.paramName2Indices[name]
        self.layers[layer_cnt].params[name] = val

    def assign_grads(self, name, val):
        # load the given values to the layer by name
        layer_cnt = self.paramName2Indices[name]
        self.layers[layer_cnt].grads[name] = val

    def get_params(self, name):
        # return the parameters by name
        return self.params[name]

    def get_grads(self, name):
        # return the gradients by name
        return self.grads[name]

    def gather_params(self):
        """
        Collect the parameters of every submodules
        """
        for layer in self.layers:
            for n, v in layer.params.items():
                self.params[n] = v

    def gather_grads(self):
        """
        Collect the gradients of every submodules
        """
        for layer in self.layers:
            for n, v in layer.grads.items():
                self.grads[n] = v

    def load(self, pretrained):
        """
        Load a pretrained model by names
        """
        for layer in self.layers:
            if not hasattr(layer, "params"):
                continue
            for n, v in layer.params.items():
                if n in pretrained.keys():
                    layer.params[n] = pretrained[n].copy()
                    print ("Loading Params: {} Shape: {}".format(n, layer.params[n].shape))


class flatten(object):
    def __init__(self, name="flatten"):
        """
        - name: the name of current layer
        - meta: to store the forward pass activations for computing backpropagation
        Note: params and grads should be just empty dicts here, do not update them
        """
        self.name = name
        self.params = {}
        self.grads = {}
        self.meta = None

    def forward(self, feat):
        output = None
        output = feat.reshape(feat.shape[0], np.prod(feat.shape[1:]))
        self.meta = feat
        return output

    def backward(self, dprev):
        feat = self.meta
        if feat is None:
            raise ValueError("No forward function called before for this module!")
        dfeat = None
        dfeat = np.transpose(self.meta.reshape(feat.shape[0], np.prod(feat.shape[1:])))
        self.meta = None
        return dfeat


class fc(object):
    def __init__(self, input_dim, output_dim, init_scale=0.02, name="fc"):
        """
        In forward pass, please use self.params for the weights and biases for this layer
        In backward pass, store the computed gradients to self.grads
        - name: the name of current layer
        - input_dim: input dimension
        - output_dim: output dimension
        - meta: to store the forward pass activations for computing backpropagation
        """
        self.name = name
        self.w_name = name + "_w"
        self.b_name = name + "_b"
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.params = {}
        self.grads = {}
        self.params[self.w_name] = init_scale * np.random.randn(input_dim, output_dim)
        self.params[self.b_name] = np.zeros(output_dim)
        self.grads[self.w_name] = None
        self.grads[self.b_name] = None
        self.meta = None

    def forward(self, feat):
        output = None
        assert np.prod(feat.shape[-1]) == self.input_dim, "But got {} and {}".format(
            np.prod(feat.shape[-1]), self.input_dim)
        # output = np.matmul(feat.reshape(feat.shape[0], np.prod(feat.shape[1:])), self.params[self.w_name]) + self.params[self.b_name]
        output = np.matmul(flatten.forward(self,feat), self.params[self.w_name]) + self.params[self.b_name]
        self.meta = feat
        return output

    def backward(self, dprev):
        feat = self.meta
        if feat is None:
            raise ValueError("No forward function called before for this module!")
        dfeat, self.grads[self.w_name], self.grads[self.b_name] = None, None, None
        assert np.prod(feat.shape[-1]) == self.input_dim, "But got {} and {}".format(
            np.prod(feat.shape[-1]), self.input_dim)
        assert np.prod(dprev.shape[-1]) == self.output_dim, "But got {} and {}".format(
            np.prod(dprev.shape[-1]), self.output_dim)
        self.grads[self.b_name] = np.sum(dprev,axis=0)
        self.grads[self.w_name] = np.matmul(flatten.backward(self,dfeat) , dprev)
        dfeat = np.matmul(dprev, np.transpose(self.params[self.w_name]))
        self.meta = None
        return dfeat


class relu(object):
    def __init__(self, name="relu"):
        """
        - name: the name of current layer
        - meta: to store the forward pass activations for computing backpropagation
        Note: params and grads should be just empty dicts here, do not update them
        """
        self.name = name
        self.params = {}
        self.grads = {}
        self.meta = None

    def forward(self, feat):
        output = None
        output = np.maximum(feat, 0)
        self.meta = feat
        return output

    def backward(self, dprev):
        """ Some comments """
        feat = self.meta
        if feat is None:
            raise ValueError("No forward function called before for this module!")
        dfeat = None
        dfeat = np.multiply(np.sign(np.abs(feat)+feat), dprev)
        self.meta = None
        return dfeat


class dropout(object):
    def __init__(self, keep_prob, seed=None, name="dropout"):
        """
        - name: the name of current layer
        - keep_prob: probability that each element is kept.
        - meta: to store the forward pass activations for computing backpropagation
        - kept: the mask for dropping out the neurons
        - is_training: dropout behaves differently during training and testing, use
                       this to indicate which phase is the current one
        - seed: numpy random seed
        Note: params and grads should be just empty dicts here, do not update them
        """
        self.name = name
        self.params = {}
        self.grads = {}
        self.keep_prob = keep_prob
        self.meta = None
        self.kept = None
        self.is_training = False
        self.seed = seed
        assert keep_prob >= 0 and keep_prob <= 1, "Keep Prob = {} is not within [0, 1]".format(keep_prob)

    def forward(self, feat, is_training=True):
        if self.seed is not None:
            np.random.seed(self.seed)
        kept = None
        output = None
        if is_training and self.keep_prob:
            tmp = np.random.rand(*feat.shape)
            kept = (tmp<=self.keep_prob)
            output = ((kept)*feat) *(1/self.keep_prob)            
        else:
            dropped = np.zeros_like(feat, dtype=bool)        
            output = feat
        self.kept = kept
        self.is_training = is_training
        self.meta = feat
        return output

    def backward(self, dprev):
        feat = self.meta
        dfeat = None
        if feat is None:
            raise ValueError("No forward function called before for this module!")
        if self.is_training and self.keep_prob:
            dfeat = dprev*(self.kept)*(1/self.keep_prob)
        else:
            dfeat = dprev
        self.is_training = False
        self.meta = None
        return dfeat


class cross_entropy(object):
    def __init__(self, size_average=True):
        """
        - size_average: if dividing by the batch size or not
        - logit: intermediate variables to store the scores
        - label: Ground truth label for classification task
        """
        self.size_average = size_average
        self.logit = None
        self.label = None

    def forward(self, feat, label):
        logit = softmax(feat)
        loss = None
        if self.size_average:
            loss = -np.sum(np.log(logit[range(0,feat.shape[0]),label])) / feat.shape[0]
        else:
            loss = -np.sum(np.log(logit[range(0,feat.shape[0]),label]))
        self.logit = logit
        self.label = label
        return loss

    def backward(self):
        logit = self.logit
        label = self.label
        if logit is None:
            raise ValueError("No forward function called before for this module!")
        dlogit = None
        m = logit.shape[0]
        dlogit = logit
        if self.size_average:
            dlogit[range(0,m),self.label] -= 1
            dlogit *= (1/m)
        else:
            dlogit[range(0,m),self.label] -= 1
        self.logit = None
        self.label = None
        return dlogit


def softmax(feat):
    scores = None
    scores = (np.exp(feat) / np.sum(np.exp(feat),axis=1,keepdims=True))
    return scores
