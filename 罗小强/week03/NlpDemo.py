# -*- coding: utf-8 -*-
"""
NlpDemo.py
描述:
作者: TomLuo 21429503@qq.com
日期: 12/4/2024
版本: 1.0
"""

import json
import random

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
class TorchModel(nn.Module):
    def __init__(self, vector_dim, sentence_length, vocab):
        super(TorchModel, self).__init__()
        self.embedding = nn.Embedding(len(vocab), vector_dim, padding_idx=0)  # embedding层
        self.lstm = nn.LSTM(vector_dim, vector_dim, batch_first=True)  # LSTM层
        self.classify = nn.Linear(vector_dim, sentence_length)  # 线性层
        self.loss = nn.functional.cross_entropy  #

    # 当输入真实标签，返回loss值；无真实标签，返回预测值
    def forward(self, x, y=None):
        x = self.embedding(x)  # (batch_size, sen_len) -> (batch_size, sen_len, vector_dim)
        x, _ = self.lstm(x)  # (batch_size, sen_len, vector_dim)
        x = x[:, -1, :]  # 取最后一个时间步的输出
        y_pred = self.classify(x)  # (batch_size, vector_dim) -> (batch_size, vector_dim)
        if y is not None:
            return self.loss(y_pred, y)  # 预测值和真实值计算损失
        else:
            return y_pred  # 输出预测结果


def build_vocab():
    chars = "你我他defghijklmnopqrstuvwxyz"  # 字符集
    vocab = {"pad": 0}
    for index, char in enumerate(chars):
        vocab[char] = index + 1  # 每个字对应一个序号
    vocab['unk'] = len(vocab)  # 26
    return vocab


def get_random_chars(vocab, special_chars, sentence_length):
    # 获取字典的所有键并转换为列表
    keys_list = list(vocab.keys())

    # 去掉“你我他”
    filtered_keys = [key for key in keys_list if key not in special_chars]

    # 随机取5个字符
    random_chars = random.sample(filtered_keys, sentence_length - 1)

    # 从“你我他”中随机取一个字符
    one_char = random.choice(special_chars)

    # 组合成一个列表
    result_list = random_chars + [one_char]
    random.shuffle(result_list)
    return result_list, one_char


# 随机生成一个样本
# 从所有字中选取sentence_length个字
# 反之为负样本
def build_sample(vocab, sentence_length):
    # 随机从字表选取sentence_length个字，可能重复
    x, one_char = get_random_chars(vocab, "我你他", sentence_length)
    y = x.index(one_char)
    x = [vocab.get(word, vocab['unk']) for word in x]  # 将字转换成序号，为了做embedding
    return x, y


# 建立数据集
# 输入需要的样本数量。需要多少生成多少
def build_dataset(sample_length, vocab, sentence_length):
    dataset_x = []
    dataset_y = []
    for i in range(sample_length):
        x, y = build_sample(vocab, sentence_length)
        dataset_x.append(x)
        dataset_y.append(y)
    return torch.LongTensor(dataset_x), torch.LongTensor(dataset_y)


# 建立模型
def build_model(vocab, char_dim, sentence_length):
    model = TorchModel(char_dim, sentence_length, vocab)
    return model


# 测试代码
# 用来测试每轮模型的准确率
def evaluate(model, vocab, sample_length):
    model.eval()
    x, y_test = build_dataset(200, vocab, sample_length)  # 建立200个用于测试的样本
    print("本次预测集中共有%d个正样本，%d个负样本" % (sum(y_test), 200 - sum(y_test)))
    with torch.no_grad():
        y_pred = model(x)  # 模型预测
        y_pred = torch.argmax(y_pred, dim=1)  # 获取预测的最大值索引
        correct, total = (y_pred == y_test).sum().item(), len(y_test)  # 计算正确预测的数量和总数量
        accuracy = correct / total  # 计算准确率
        print(f"Correct: {correct} Total: {total} Accuracy: {accuracy:.4f}")
        return accuracy


def main():
    # 配置参数
    epoch_num = 10  # 训练轮数
    batch_size = 20  # 每次训练样本个数
    train_sample = 500  # 每轮训练总共训练的样本总数
    char_dim = 20  # 每个字的维度
    sentence_length = 6  # 样本文本长度
    learning_rate = 0.005  # 学习率
    # 建立字表
    vocab = build_vocab()
    # 建立模型
    model = build_model(vocab, char_dim, sentence_length)
    # 选择优化器
    optim = torch.optim.Adam(model.parameters(), lr=learning_rate)
    log = []
    # 训练过程
    for epoch in range(epoch_num):
        model.train()
        watch_loss = []
        for batch in range(int(train_sample / batch_size)):
            x, y = build_dataset(batch_size, vocab, sentence_length)  # 构造一组训练样本
            optim.zero_grad()  # 梯度归零
            loss = model(x, y)  # 计算loss
            loss.backward()  # 计算梯度
            optim.step()  # 更新权重
            watch_loss.append(loss.item())
        print("=========\n第%d轮平均loss:%f" % (epoch + 1, np.mean(watch_loss)))
        acc = evaluate(model, vocab, sentence_length)  # 测试本轮模型结果
        log.append([acc, np.mean(watch_loss)])
    # 画图
    plt.plot(range(len(log)), [l[0] for l in log], label="acc")  # 画acc曲线
    plt.plot(range(len(log)), [l[1] for l in log], label="loss")  # 画loss曲线
    plt.legend()
    plt.show()
    # 保存模型
    torch.save(model.state_dict(), "model.checkpoint")
    # 保存词表
    with open("vocab.json", "w", encoding="utf8") as writer:
        writer.write(json.dumps(vocab, ensure_ascii=False, indent=2))
    return


# 使用训练好的模型做预测
def predict(model_path, vocab_path, input_strings):
    char_dim = 20  # 每个字的维度
    sentence_length = 6  # 样本文本长度
    vocab = json.load(open(vocab_path, "r", encoding="utf8"))  # 加载字符表
    model = build_model(vocab, char_dim, sentence_length)  # 建立模型
    model.load_state_dict(torch.load(model_path,weights_only=True))  # 加载训练好的权重
    x = []
    for input_string in input_strings:
        x.append([vocab[char] for char in input_string])  # 将输入序列化
    model.eval()  # 测试模式
    result = []
    with torch.no_grad():  # 不计算梯度
        y_pred = model.forward(torch.LongTensor(x))  # 模型预测
        y_pred_max = torch.argmax(y_pred, dim=1)  # 获取预测的最大值索引
        for x_t, y_p, y_p_max in zip(input_strings, y_pred, y_pred_max):
            print("input:{} y_pred:{} predict:{}".format(x_t, y_p, y_p_max))  # 打印输入和预测结果


if __name__ == "__main__":
    main()
    test_strings = ["fnvfe你", "wz你dfg", "rqw你eg", "n我kwww"]
    predict("model.checkpoint", "vocab.json", test_strings)
