import dataset
import lm

import torch
import torch.optim as optim

import numpy as np
from tqdm import tqdm
from Optim import ScheduledOptim

import config
import logger
import time
import math

use_cuda = torch.cuda.is_available

def pack(arr, size):
    batch = [arr[i:i+size] for i in range(0, len(arr), size)]
    return batch

class Trainer:
    def __init__(self):
        self.ds_train = dataset.Dataset(config.trainPath, config.dictPath)
        self.ds_valid = dataset.Dataset(config.validPath, config.dictPath)
        self.ds_test = dataset.Dataset(config.testPath, config.dictPath)
        
        vocSize = len(self.ds_train.word2id)
        maxSeqLen = max([len(idLine) for idLine in self.ds_train.idData])
        padId = self.ds_train.word2id['<PAD>']
        self.model = lm.LM(vocSize, maxSeqLen, padId)
        # vocSize+1 for padding indice

        self.loss_log = logger.Logger('../result/loss.log')
        self.eval_log = logger.Logger('../result/eval.log')

    def train(self, maxEpoch):
        if use_cuda:
            print('use cuda')
            self.model = self.model.cuda()
            self.model.use_cuda = True
            self.model.tensor = torch.cuda.LongTensor

        self.model.train()
        #opt = optim.Adam(self.model.parameters(),betas=(0.9, 0.98), eps=1e-09)
        #opt = optim.Adam(self.model.parameters())

        opt = ScheduledOptim(
            optim.Adam(
                filter(lambda x: x.requires_grad, self.model.parameters()),
                betas=(0.9, 0.98), eps=1e-09),
            config.d_model, config.n_warmup_steps)

        for ep in range(maxEpoch):
            start = time.time()
            print(ep)
            indices = np.random.permutation(len(self.ds_train.idData))
            batches = pack(indices, 64)

            accLoss = 0
            n_word_total = 0
            n_word_correct = 0
            for batch in tqdm(batches):
                opt.zero_grad()
                idLines = [self.ds_train.idData[b] for b in batch]
                loss, n_correct,ts = self.model.getLoss(idLines)

                # backward and update
                loss.backward()
                opt.step_and_update_lr()

                # keep info
                accLoss += loss.item()
                non_pad_mask = ts.ne(config.pad_id)
                n_word = non_pad_mask.sum().item()
                n_word_total += n_word
                n_word_correct += n_correct

            loss_per_word = accLoss/n_word_total
            accuracy = n_word_correct/n_word_total

            print('  - (Train) ppl: {ppl: 8.5f}, accuracy: {accu:3.3f} %, '\
                        'elapse: {elapse:3.3f} min'.format(
                        ppl=math.exp(min(loss_per_word, 100)), accu=100*accuracy,
                        elapse=(time.time()-start)/60))

            self.evaluate()

    def evaluate(self):
        self.model.eval()
        if use_cuda:
            print('use cuda')
            self.model = self.model.cuda()
            self.model.use_cuda = True
            self.model.tensor = torch.cuda.LongTensor

        reports = []
        result = []

        for ds in [self.ds_train, self.ds_valid, self.ds_test]: 
            start = time.time()

            psum = 0
            size = 0

            accLoss = 0
            n_word_total = 0
            n_word_correct = 0
            
            batches = pack(np.arange(len(ds.idData)),64)
          
            show = False
            for batch in tqdm(batches):
                loss, n_correct,ts = self.model.getLoss([ds.idData[b] for b in batch]) 
                if show:
                    flag = 0
                    for b in batch:
                        idLine = ds.idData[b][:-1]
                        print(' '.join([ds.id2word[w] for w in idLine]))
                        print(' '.join([ds.id2word[w.data.tolist()] for w in preds[flag:flag+len(idLine)]]))
                        flag += len(idLine)
                    show = False
                # keep info
                
                accLoss += loss.item()
                non_pad_mask = ts.ne(config.pad_id)
                n_word = non_pad_mask.sum().item()
                n_word_total += n_word
                n_word_correct += n_correct
           
            loss_per_word = accLoss/n_word_total
            accuracy = n_word_correct/n_word_total

            report = '- ppl: {ppl: 8.5f}, accuracy: {accu:3.3f} %, '\
                     'elapse: {elapse:3.3f} min'.format(
                     ppl=math.exp(min(loss_per_word, 100)), accu=100*accuracy,
                     elapse=(time.time()-start)/60)
            reports.append(report)

            result.append(math.exp(min(loss_per_word, 100)))
        
        # show reports
        for t,r in zip(['train','valid','test'],reports):
            print('(%s)'%t+r)

        result = [str(r) for r in result]
        self.eval_log.write('\t'.join(result))

        self.model.train()
        print('')

if __name__ == '__main__':
    t = Trainer()
    t.train(config.maxEpoch)
    #t.evaluate()
