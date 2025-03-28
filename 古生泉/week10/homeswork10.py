# coding:utf8

import torch
import torch.nn as nn
import numpy as np
import math
import random
import os
import re

from transformers import BertModel, BertTokenizer

"""
基于pytorch的LSTM语言模型
"""


class LanguageModel(nn.Module):
    def __init__(self, input_dim, vocab_size):
        super(LanguageModel, self).__init__()
        # self.embedding = nn.Embedding(len(vocab), input_dim)
        # self.layer = nn.LSTM(input_dim, input_dim, num_layers=1, batch_first=True)
        self.bert = BertModel.from_pretrained(r"D:\Python\PythonAi\pythonAi\model\bert-base-chinese", return_dict=False)
        self.classify = nn.Linear(input_dim, vocab_size)
        # self.dropout = nn.Dropout(0.1)
        self.loss = nn.functional.cross_entropy

    # 当输入真实标签，返回loss值；无真实标签，返回预测值
    def forward(self, x, y=None):
        if y is not None:
            mask = torch.tril(torch.ones(x.shape[0], x.shape[1], x.shape[1]))
            # print(mask)
            x, _ = self.bert(x, attention_mask=mask)
            y_pred = self.classify(x)
            return self.loss(y_pred.view(-1, y_pred.shape[-1]), y.view(-1))
        else:
            x = self.bert(x)[0]
            y_pred = self.classify(x)
            return torch.softmax(y_pred, dim=-1)


# 加载字表
def build_vocab(vocab_path):
    vocab = {"<pad>": 0}
    with open(vocab_path, encoding="utf8") as f:
        for index, line in enumerate(f):
            char = line[:-1]  # 去掉结尾换行符
            vocab[char] = index + 1  # 留出0位给pad token
    return vocab


# 加载语料
def load_corpus(path):
    corpus = ""
    with open(path, encoding="gbk") as f:
        for line in f:
            corpus += line.strip()
    return corpus


# 随机生成一个样本
# 从文本中截取随机窗口，前n个字作为输入，最后一个字作为输出
def build_sample(tokenizer, window_size, corpus):
    start = random.randint(0, len(corpus) - 1 - window_size)
    end = start + window_size
    window = corpus[start:end]
    target = corpus[start + 1:end + 1]  # 输入输出错开一位
    # print(window, target)
    # 中文的文本转化为tokenizer的id
    input_ids_x = tokenizer.encode(window, add_special_tokens=False, padding='max_length', truncation=True,
                                   max_length=10)
    input_ids_y = tokenizer.encode(target, add_special_tokens=False, padding='max_length', truncation=True,
                                   max_length=10)
    return input_ids_x, input_ids_y


# 建立数据集
# sample_length 输入需要的样本数量。需要多少生成多少
# vocab 词表
# window_size 样本长度
# corpus 语料字符串
def build_dataset(sample_length, tokenizer, window_size, corpus):
    dataset_x = []
    dataset_y = []
    for i in range(sample_length):
        x, y = build_sample(tokenizer, window_size, corpus)
        dataset_x.append(x)
        dataset_y.append(y)
    return torch.LongTensor(dataset_x), torch.LongTensor(dataset_y)


# 建立模型
def build_model(vocab_size, char_dim):
    model = LanguageModel(char_dim, vocab_size)
    return model


# 文本生成测试代码
def generate_sentence(openings, model, tokenizer,tokenizer_vovab, window_size):
    reverse_vocab = dict((y, x) for x, y in tokenizer_vovab.items())
    model.eval()
    with torch.no_grad():
        pred_char = ""
        # 生成文本超过30字终止
        while len(openings) <= 30:
            openings += pred_char
            x = tokenizer.encode(openings, add_special_tokens=False, padding='max_length', truncation=True,
                                 max_length=10)
            x = torch.LongTensor([x])
            if torch.cuda.is_available():
                x = x.cuda()
            # batch_size = 1 最后一个字符的概率
            y = model(x)[0][-1]
            index = sampling_strategy(y)
            # 转化为中文 只有一个字符
            # pred_char = tokenizer.decode(index)
            pred_char = reverse_vocab[index]
    return openings


# 采样方式
def sampling_strategy(prob_distribution):
    if random.random() > 0.1:
        strategy = "greedy"
    else:
        strategy = "sampling"
    if strategy == "greedy":
        return int(torch.argmax(prob_distribution))
    elif strategy == "sampling":
        prob_distribution = prob_distribution.cpu().numpy()
        return np.random.choice(list(range(len(prob_distribution))), p=prob_distribution)


# 计算文本ppl
def calc_perplexity(sentence, model, vocab, window_size):
    prob = 0
    model.eval()
    with torch.no_grad():
        for i in range(1, len(sentence)):
            start = max(0, i - window_size)
            window = sentence[start:i]
            x = [vocab.get(char, vocab["<UNK>"]) for char in window]
            x = torch.LongTensor([x])
            target = sentence[i]
            target_index = vocab.get(target, vocab["<UNK>"])
            if torch.cuda.is_available():
                x = x.cuda()
            pred_prob_distribute = model(x)[0][-1]
            target_prob = pred_prob_distribute[target_index]
            prob += math.log(target_prob, 10)
    return 2 ** (prob * (-1 / len(sentence)))


def train(corpus_path, save_weight=True):
    epoch_num = 15  # 训练轮数
    batch_size = 64  # 每次训练样本个数
    train_sample = 10000  # 每轮训练总共训练的样本总数
    char_dim = 768  # 每个字的维度
    window_size = 10  # 样本文本长度
    # vocab = build_vocab(r"vocab.txt")  # 建立字表
    tokenizer = BertTokenizer.from_pretrained(r"D:\Python\PythonAi\pythonAi\model\bert-base-chinese")
    tokenizer_vovab = tokenizer.vocab
    vocab_size = len(tokenizer_vovab)
    corpus = load_corpus(corpus_path)  # 加载语料
    model = build_model(vocab_size, char_dim)  # 建立模型
    if torch.cuda.is_available():
        model = model.cuda()
    optim = torch.optim.Adam(model.parameters(), lr=0.001)  # 建立优化器
    print("文本词表模型加载完毕，开始训练")
    for epoch in range(epoch_num):
        model.train()
        watch_loss = []
        for batch in range(int(train_sample / batch_size)):
            x, y = build_dataset(batch_size, tokenizer, window_size, corpus)  # 构建一组训练样本
            if torch.cuda.is_available():
                x, y = x.cuda(), y.cuda()
            optim.zero_grad()  # 梯度归零
            loss = model(x, y)  # 计算loss
            loss.backward()  # 计算梯度
            optim.step()  # 更新权重
            watch_loss.append(loss.item())
        print("=========\n第%d轮平均loss:%f" % (epoch + 1, np.mean(watch_loss)))
        print(generate_sentence("让他在半年之前，就不能做出", model, tokenizer,tokenizer_vovab, window_size))
        print(generate_sentence("李慕站在山路上，深深的呼吸", model, tokenizer,tokenizer_vovab, window_size))
    if not save_weight:
        return
    else:
        base_name = os.path.basename(corpus_path).replace("txt", "pth")
        model_path = os.path.join("model", base_name)
        torch.save(model.state_dict(), model_path)
        return


if __name__ == "__main__":
    train(r"D:\Python\PythonAi\pythonAi\week10\yuxi10\lstm语言模型生成文本\corpus.txt", False)



