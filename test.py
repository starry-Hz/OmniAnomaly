import subprocess
import os
import datetime
import threading
from queue import Queue

# 定义文件列表
file_list = [
    'machine-1-1.txt', 'machine-1-6.txt', 'machine-1-7.txt',
    'machine-2-1.txt', 'machine-2-2.txt', 'machine-2-3.txt',
    'machine-2-4.txt', 'machine-2-7.txt', 'machine-2-8.txt',
    'machine-3-3.txt', 'machine-3-4.txt', 'machine-3-6.txt',
    'machine-3-8.txt', 'machine-3-10.txt', 'machine-3-11.txt'
]
# file_list = [f"omi-{i}.txt" for i in range(1, 2)]

current_date = datetime.datetime.now().strftime("%Y%m%d")

# 创建线程安全的队列和失败任务列表
task_queue = Queue()
failed_tasks = []
lock = threading.Lock()

# 将任务放入队列
for file in file_list:
    task_queue.put(file)

# 工作线程函数
def worker(thread_id):
    while not task_queue.empty():
        try:
            file = task_queue.get_nowait()
        except:
            break  # 队列已空
            
        dataset_name = file[:-4]  # 去掉.txt后缀
        log_file = f"location_log/SMD_{current_date}/{dataset_name}.log"
        
        print(f"线程{thread_id} ➡️ 正在执行: {dataset_name}")

        command = [
            'python', 'main.py',
            f'--dataset={dataset_name}',
            '--max_epoch=10'
        ]
        
        try:
            with open(log_file, 'w') as f:
                process = subprocess.Popen(command, stdout=f, stderr=subprocess.STDOUT)
                exit_code = process.wait()  # 等待进程结束

            if exit_code != 0:
                print(f"线程{thread_id} ⚠️  {dataset_name} 执行失败（退出码: {exit_code}），请查看日志：{log_file}")
                with lock:
                    failed_tasks.append(dataset_name)
            else:
                print(f"线程{thread_id} ✅  {dataset_name} 执行完成，日志保存在：{log_file}")

        except Exception as e:
            print(f"线程{thread_id} ❌  {dataset_name} 执行过程中发生异常：{e}")
            with lock:
                failed_tasks.append(dataset_name)
        
        task_queue.task_done()

# 如果日志目录不存在则创建
os.makedirs(f"location_log/SMD_{current_date}", exist_ok=True)

# 创建并启动两个工作线程
threads = []
for i in range(1):
    t = threading.Thread(target=worker, args=(i+1,))
    t.start()
    threads.append(t)

# 等待所有任务完成
task_queue.join()

# 等待所有线程完成
for t in threads:
    t.join()

print("\n🔚 所有数据集已处理完毕。")

if failed_tasks:
    print("以下任务执行失败，请检查日志：")
    for task in failed_tasks:
        print(f" - {task}")
else:
    print("🎉 所有任务均执行成功！")

# file_list = [f"omi-{i}.txt" for i in range(1, 13)]
# print(file_list)
# ['omi-1.txt', 'omi-2.txt', 'omi-3.txt', 'omi-4.txt', 'omi-5.txt', 'omi-6.txt', 'omi-7.txt', 'omi-8.txt', 'omi-9.txt', 'omi-10.txt', 'omi-11.txt', 'omi-12.txt']
# (py36) hz@gpu-sys:~/code/OmniAnomaly$ nohup python test.py > location_log/SMD_20250610/SMD.log 2>&1 &