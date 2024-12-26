在Linux服务器后台运行命令

方法一：使用nohup

nohup python main.py --dataset='SWAT_down' > output.log 2>&1 &

**解释：**

1. **`nohup`** ：使程序在用户退出会话后继续运行。
2. **`>`** ：将标准输出（`stdout`）重定向到文件 `output.log`。
3. **`2>&1`** ：将标准错误（`stderr`）重定向到标准输出，使错误也写入 `output.log`。
4. **`&`** ：将命令放入后台运行。

方法二：使用screen

1. 启动新的 `screen`会话：

   ```bash 
   screen -S swat_down_session
   ```

2.在新会话中运行你的命令：

   ```bash
   python main.py --dataset='SWAT_down'
   ```
   
3.按下`ctrl+A`,然后按`D`退出 `screen` 会话,程序会继续后台运行
4.重新连接到会话:
   ```bash
   screen -r swat_down_session
   ```

方法三：使用`tmux`

1. 启动一个 `tmux` 会话：

   ```bash 
   tmux new -s swat_down_session
   ```
2.在会话中运行命令：

   ```bash
   python main.py --dataset='SWAT_down'
   ```
3.分离会话：按下 `Ctrl+B`，然后按 `D`
4.重新连接到会话:
   ```bash
   tmux attach -t swat_down_session
   ```

方法 4：使用 `&` 和 `disown`
1.直接将命令后台运行：
   ```bash
   python main.py --dataset='SWAT_down' > output.log 2>&1 &
   ```
2.将任务从当前会话中分离:
   ```bash
   disown
   ```