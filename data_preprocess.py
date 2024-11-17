import ast
import csv
import os
import sys
from pickle import dump

import numpy as np
# from tfsnippet.utils import makedirs

# output_folder = 'processed'
# makedirs(output_folder, exist_ok=True)
import os
# 替代 tfsnippet.utils.makedirs
output_folder = 'processed'
os.makedirs(output_folder, exist_ok=True)


def load_and_save(category, filename, dataset, dataset_folder):
    '''
    category : 文件夹
    filename : 要加载的数据文件名
    dataset : 数据集名称
    dataset_folder : 数据集所在的文件夹路径
    '''
    # np.genfromtxt()：用于从文本文件中加载数据,按行读取,并将其解析成数组
    temp = np.genfromtxt(os.path.join(dataset_folder, category, filename),
                         dtype=np.float32,
                         delimiter=',') # ,为分隔符
    print(dataset, category, filename, temp.shape)
    # 文件名：  dataset + "_" + category + ".pkl"    wb以二进制写入模式打开文件
    with open(os.path.join(output_folder, dataset + "_" + category + ".pkl"), "wb") as file:
        dump(temp, file)    # 使用 pickle 模块的 dump() 方法将 temp 序列化并保存到 .pkl 文件中


def load_data(dataset):
    if dataset == 'SMD':
        dataset_folder = 'ServerMachineDataset'
        # 列出 train 文件夹中的所有文件 (os.listdir())，并遍历文件名
        file_list = os.listdir(os.path.join(dataset_folder, "train"))
        # 对每个以 .txt 结尾的文件，调用 load_and_save() 函数三次：
        for filename in file_list:
            if filename.endswith('.txt'):
                load_and_save('train', filename, filename.strip('.txt'), dataset_folder)
                load_and_save('test', filename, filename.strip('.txt'), dataset_folder)
                load_and_save('test_label', filename, filename.strip('.txt'), dataset_folder)
    elif dataset == 'SMAP' or dataset == 'MSL':
        dataset_folder = 'data'
        # 读取文件中的每个数据文件的异常标签
        with open(os.path.join(dataset_folder, 'labeled_anomalies.csv'), 'r') as file:
            csv_reader = csv.reader(file, delimiter=',')
            res = [row for row in csv_reader][1:]
        # 将 res 列表按每一行的第一个元素（通常是文件名）进行排序。这是为了确保处理数据时按正确的顺序加载数据
        res = sorted(res, key=lambda k: k[0])
        label_folder = os.path.join(dataset_folder, 'test_label')
        # makedirs(label_folder, exist_ok=True)
        os.makedirs(label_folder, exist_ok=True)
        # 用于排除文件名为 'P-2' 的数据行
        data_info = [row for row in res if row[1] == dataset and row[0] != 'P-2']
        labels = []
        for row in data_info:
            anomalies = ast.literal_eval(row[2])    # 将字符串形式的异常位置转换为 Python 对象（列表）。例如，row[2] 可能是 [(10, 20), (30, 40)]，表示异常的区间
            length = int(row[-1])
            # label = np.zeros([length], dtype=np.bool)
            label = np.zeros([length], dtype=bool)  # 使用内建的 bool 类型
            for anomaly in anomalies:   # 将异常的位置标记为 True
                label[anomaly[0]:anomaly[1] + 1] = True
            labels.extend(label)
        labels = np.asarray(labels) # 将 labels 列表转换为 NumPy 数组
        print(dataset, 'test_label', labels.shape)
        # print(os.path.join(output_folder, dataset + "_" + 'test_label' + ".pkl"))   # processed/MSL_test_label.pkl
        with open(os.path.join(output_folder, dataset + "_" + 'test_label' + ".pkl"), "wb") as file:
            dump(labels, file)

        def concatenate_and_save(category):
            data = []
            for row in data_info:
                filename = row[0]
                temp = np.load(os.path.join(dataset_folder, category, filename + '.npy'))
                data.extend(temp)
            data = np.asarray(data)
            print(dataset, category, data.shape)
            with open(os.path.join(output_folder, dataset + "_" + category + ".pkl"), "wb") as file:
                dump(data, file)

        # 分别加载训练数据和测试数据
        for c in ['train', 'test']:
            concatenate_and_save(c)


if __name__ == '__main__':
    # datasets = ['SMD', 'SMAP', 'MSL']
    # # datasets = ['SMD']
    # commands = sys.argv[1:]
    # load = []
    # if len(commands) > 0:
    #     for d in commands:
    #         if d in datasets:
    #             load_data(d)
    # else:
    #     print("""
    #     Usage: python data_preprocess.py <datasets>
    #     where <datasets> should be one of ['SMD', 'SMAP', 'MSL']
    #     """)
    dataset = 'MSL'
    # dataset = ['SMAP', 'MSL']
    load_data(dataset)