import subprocess
import os
import datetime

# 定义文件列表
file_list_machine = [
    'machine-1-1.txt', 'machine-1-6.txt', 'machine-1-7.txt',
    'machine-2-1.txt', 'machine-2-2.txt', 'machine-2-3.txt',
    'machine-2-4.txt', 'machine-2-7.txt', 'machine-2-8.txt',
    'machine-3-3.txt', 'machine-3-4.txt', 'machine-3-6.txt',
    'machine-3-8.txt', 'machine-3-10.txt', 'machine-3-11.txt'
]
file_omi_list = [f"omi-{i}.txt" for i in range(1, 13)]
file_list = file_omi_list + file_list_machine
percentage_Dimension = [20, 30, 40, 50]
current_date = datetime.datetime.now().strftime("%Y%m%d")

# 失败任务列表
failed_tasks = []

def run_single_task(file, percentage):
    dataset_name = file[:-4]  # 去掉.txt后缀
    # 获取文件名的前缀部分（兼容omi和machine两种格式）
    file_name = file.split('-')[0] if '-' in file else file.split('_')[0]
    log_dir = f"location_log/{file_name}_{current_date}/p{percentage}"
    log_file = f"{log_dir}/{dataset_name}.log"  # 简化日志文件名
    
    print(f"\n➡️ 正在执行: {dataset_name} (percentage={percentage})")
    print(f"日志文件将保存到: {log_file}")

    command = [
        'python', 'main.py',
        f'--dataset={dataset_name}',
        '--max_epoch=10',
        f'--percentage_Dimension={percentage}',
    ]
    
    try:
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
        
        with open(log_file, 'w') as f:
            process = subprocess.Popen(command, stdout=f, stderr=subprocess.STDOUT)
            exit_code = process.wait()  # 等待进程结束

        if exit_code != 0:
            print(f"⚠️ {dataset_name} (p={percentage}) 执行失败（退出码: {exit_code}）")
            failed_tasks.append((dataset_name, percentage, log_file))
        else:
            print(f"✅ {dataset_name} (p={percentage}) 执行完成")

    except Exception as e:
        print(f"❌ {dataset_name} (p={percentage}) 执行过程中发生异常：{str(e)}")
        failed_tasks.append((dataset_name, percentage, log_file))

if __name__ == "__main__":
    print(f"📅 开始执行任务，当前日期: {current_date}")
    print(f"📂 待处理文件数量: {len(file_list)}")
    print(f"🔢 待测试的percentage_Dimension值: {percentage_Dimension}")
    
    # 主循环：先按percentage循环，再按文件循环
    for percentage in percentage_Dimension:
        print(f"\n🔄 开始处理 percentage_Dimension={percentage} 的任务...")
        for file in file_list:
            run_single_task(file, percentage)
        print(f"✅ 已完成 percentage_Dimension={percentage} 的所有任务")

    print("\n" + "="*50)
    print("🔚 所有数据集已处理完毕。统计结果:")

    if failed_tasks:
        print("\n以下任务执行失败，请检查对应日志：")
        for task in failed_tasks:
            print(f" - 数据集: {task[0]}, percentage: {task[1]}, 日志路径: {task[2]}")
        print(f"\n❌ 失败任务数量: {len(failed_tasks)}/{len(file_list)*len(percentage_Dimension)}")
    else:
        print("\n🎉 所有任务均执行成功！")

    print("\n执行结束。")