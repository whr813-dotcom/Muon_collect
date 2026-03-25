import pyvisa as vi
import io
import pandas as pd
import time
import struct
import numpy as np


def connect_to_scope():
    rm = vi.ResourceManager()
    try:
        # 1. 设置连接参数
        inst = rm.open_resource(
            "USB0::0x0957::0x1796::MY52160509::0::INSTR", open_timeout=5000
        )

        # 2. 关键设置：Agilent 示波器必须设置读写结束符
        inst.read_termination = "\n"
        inst.write_termination = "\n"

        # 3. 设置超时时间 (60秒)，读取大量数据需要时间
        inst.timeout = 60000
        inst.chunk_size = 1024000  # 增加缓冲区以处理二进制数据

        # 4. 初始化：清除状态，复位
        inst.write("*CLS")
        inst.write(":SYSTem:HEADer OFF")  # 关闭响应头，只返回数据

        idn = inst.query("*IDN?")
        print(f"Success Connected to: {idn}")

    except Exception as e:
        print(f"Unable to open instruments: {e}")
        return 0
    return inst


def get_channel_status(inst):
    """
    检查哪些通道是打开的
    """
    open_channel = []
    try:
        for i in range(1, 5):
            resp = inst.query(f":CHANnel{i}:DISPlay?")
            if int(resp) == 1:
                open_channel.append(i)
    except Exception as exce:
        print(f"Check channel error: {exce}")

    print(f"Active Channels found: {open_channel}")
    return open_channel


def setup_waveform_params(inst, channel, points=10000):
    """
    设置波形读取参数
    """
    inst.write(f":WAVeform:SOURce CHANnel{channel}")
    inst.write(":WAVeform:FORMat WORD")  # 使用WORD格式（16位有符号整数）
    inst.write(":WAVeform:UNSigned OFF")  # 使用有符号数据
    inst.write(":WAVeform:BYTeorder LSBFirst")  # 字节序
    inst.write(f":WAVeform:POINts {points}")
    inst.write(":WAVeform:POINts:MODE RAW")  # 获取原始数据
    time.sleep(0.1)  # 等待示波器准备好


def parse_tmc_header(data):
    """
    解析TMC格式的头部信息
    格式: #NXXXXXXX... 其中N是数字位数，XXXXXXX是数据长度
    """
    if not data.startswith(b"#"):
        return 0, data

    # 获取头部长度信息
    num_digits = int(chr(data[1]))  # #后面的数字表示长度字段的位数
    data_len_str = data[2 : 2 + num_digits].decode("ascii")
    data_len = int(data_len_str)

    # 返回数据部分的起始位置和数据长度
    header_len = 2 + num_digits
    return header_len, data_len


def read_waveform_data(inst):
    """
    读取波形数据并转换为电压值
    """
    try:
        current_source = inst.query(":WAVeform:SOURce?")
        print(f"  Current waveform source: {current_source.strip()}")

        # 获取波形前导信息
        preamble = inst.query(":WAVeform:PREamble?").strip().split(",")

        # 解析前导信息
        # 格式: format, type, points, count, xincrement, xorigin, xreference, yincrement, yorigin, yreference
        if len(preamble) < 10:
            # 尝试另一种可能的格式
            preamble = inst.query(":WAVeform:PREamble?").strip()
            print(f"Raw preamble: {preamble}")
            return pd.Series()

        points = int(preamble[2])
        x_increment = float(preamble[4])
        x_origin = float(preamble[5])
        x_reference = float(preamble[6])
        y_increment = float(preamble[7])
        y_origin = float(preamble[8])
        y_reference = float(preamble[9])

        print(
            f"  y_increment: {y_increment}, y_origin: {y_origin}, y_reference: {y_reference}"
        )

        # 读取波形数据
        inst.write(":WAVeform:DATA?")

        # 读取原始数据（二进制）
        raw_data = inst.read_raw()

        # 解析TMC头部
        header_len, data_len = parse_tmc_header(raw_data)

        if header_len == 0:
            print("Warning: No TMC header found, trying ASCII parsing")
            # 尝试作为ASCII解析
            data_str = raw_data.decode("ascii", errors="ignore").strip()
            # 移除可能的分隔符
            if data_str.startswith("#"):
                # 手动解析TMC格式的ASCII
                num_digits = int(data_str[1])
                data_start = 2 + num_digits
                data_str = data_str[data_start:]

            # 分割数据
            data_list = []
            current_num = ""
            for char in data_str:
                if char == "," or char == " " or char == "\n" or char == "\r":
                    if current_num:
                        try:
                            data_list.append(float(current_num))
                        except:
                            pass
                        current_num = ""
                else:
                    current_num += char

            if current_num:
                try:
                    data_list.append(float(current_num))
                except:
                    pass

            if len(data_list) == 0:
                # 尝试直接分割
                data_list = [float(x) for x in data_str.replace(",", " ").split() if x]

            data_points = np.array(data_list)
        else:
            # 解析二进制数据
            binary_data = raw_data[header_len : header_len + data_len]

            # 根据前导信息中的format处理数据
            # format=0: BYTE (8-bit), format=1: WORD (16-bit), format=2: ASCii
            format_type = int(preamble[0])

            if format_type == 1:  # WORD格式 (16-bit)
                # 16位有符号整数，小端序
                data_points = np.frombuffer(binary_data, dtype="<i2", count=points)
            elif format_type == 0:  # BYTE格式 (8-bit)
                data_points = np.frombuffer(binary_data, dtype="b", count=points)
            else:  # ASCII格式
                data_str = binary_data.decode("ascii", errors="ignore")
                data_points = np.array([float(x) for x in data_str.split(",") if x])

        # 将数据点转换为电压值
        # 公式: voltage = (data_value - y_reference) * y_increment + y_origin
        voltages = (data_points - y_reference) * y_increment + y_origin

        # 创建时间轴
        times = np.arange(points) * x_increment + x_origin

        # 创建DataFrame
        df = pd.DataFrame({"Time": times, "Voltage": voltages})

        return df

    except Exception as e:
        print(f"Data process error: {e}")
        import traceback

        traceback.print_exc()
        raise e


def wait_for_trigger(inst):
    """
    等待触发完成
    """
    max_wait_time = 30  # 最大等待时间（秒）
    start_time = time.time()

    while True:
        try:
            # 检查运行状态
            status = int(inst.query(":OPERegister:CONDition?"))

            # 位3 (值为8) 表示正在运行
            if not (status & 8):  # 如果第3位是0，说明Scope已经停止（触发完成）
                return True

            # 检查是否超时
            if time.time() - start_time > max_wait_time:
                print("Trigger wait timeout")
                return False

            time.sleep(0.1)

        except Exception as e:
            print(f"Trigger wait error: {e}")
            time.sleep(1)
            return False


def start_acquire(entries=5, points=10000, outfile_prefix="agilent_data"):
    inst = connect_to_scope()
    if inst == 0:
        return

    OC = get_channel_status(inst)
    if not OC:
        print("Error: No active channels found. Please enable a channel on the scope.")
        return

    # 设置采集模式
    inst.write(":ACQuire:TYPE NORMal")
    inst.write(":ACQuire:COMPlete 100")  # 设置采集完成百分比

    # 设置时间基准
    inst.write(":TIMebase:MODE MAIN")
    inst.write(f":TIMebase:SCALe {1e-3}")  # 1ms/div 示例，根据需要调整
    inst.write(f":TIMebase:POSition {0}")  # 触发位置

    # 停止示波器以进行设置
    inst.write(":STOP")

    # 文件名
    outfile = f"{outfile_prefix}_{time.strftime('%Y-%m-%d-%H-%M-%S')}.csv"
    print(f"Output file: {outfile}")

    # 创建输出文件并写入表头
    with open(outfile, "w") as f:
        header = "Event,Time,Voltage1,Voltage2"
        f.write(header + "\n")

    event_count = 0

    for j in range(entries):
        try:
            print(f"\nStarting acquisition {j + 1}/{entries}")

            # 启动单次采集
            inst.write(":SINGle")

            # 等待触发
            if wait_for_trigger(inst):
                print(f"Trigger captured for event {j + 1}")

                # 先读取所有通道的数据
                all_channel_data = {}
                for ch in OC:
                    try:
                        print(f"  Reading channel {ch}...")

                        # 设置波形参数
                        setup_waveform_params(inst, ch, points)

                        # 获取数据（带重试机制）
                        df_channel = pd.Series()
                        for retry in range(3):
                            df_channel = read_waveform_data(inst)
                            if not df_channel.empty:
                                break
                            print(f"  Retry {retry + 1} for channel {ch}...")
                            time.sleep(0.2)

                        if df_channel.empty:
                            print(f"  Warning: No data received for channel {ch}")
                            continue

                        all_channel_data[ch] = df_channel
                        print(f"  Channel {ch}: {len(df_channel)} points")

                    except Exception as e:
                        print(f"  Error reading Channel {ch}: {e}")

                # 合并所有通道数据到同一行
                if len(all_channel_data) > 0:
                    # 信号阈值过滤
                    max_v1 = (
                        abs(all_channel_data[1]["Voltage"].max())
                        if 1 in all_channel_data
                        else 0
                    )
                    max_v2 = (
                        abs(all_channel_data[2]["Voltage"].max())
                        if 2 in all_channel_data
                        else 0
                    )
                    if max_v1 < 0.01 and max_v2 < 0.01:
                        print(
                            f"  Skipping event {j + 1}: signal too small (max_v1={max_v1:.4f}, max_v2={max_v2:.4f})"
                        )

                        # 重置示波器继续下一个事件
                        inst.write("*CLS")
                        inst.write(":STOP")
                        continue
                    # 获取第一个通道的时间作为基准
                    first_ch = list(all_channel_data.keys())[0]
                    base_times = all_channel_data[first_ch]["Time"].values
                    min_points = len(base_times)

                    # 确保所有通道数据长度一致
                    for ch, df in all_channel_data.items():
                        if len(df) < min_points:
                            min_points = len(df)

                    # 写入合并后的数据
                    with open(outfile, "a") as f:
                        for i in range(min_points):
                            time_val = base_times[i]
                            voltage1 = (
                                all_channel_data[1]["Voltage"].values[i]
                                if 1 in all_channel_data
                                else ""
                            )
                            voltage2 = (
                                all_channel_data[2]["Voltage"].values[i]
                                if 2 in all_channel_data
                                else ""
                            )
                            if voltage1 != "" and voltage2 != "":
                                f.write(
                                    f"{j + 1},{time_val:.9e},{voltage1:.9e},{voltage2:.9e}\n"
                                )
                            elif voltage1 != "":
                                f.write(f"{j + 1},{time_val:.9e},{voltage1:.9e},\n")
                            elif voltage2 != "":
                                f.write(f"{j + 1},{time_val:.9e},\n")

                    print(f"  Event {j + 1}: {min_points} points saved")

                    event_count += 1
                    print(f"Event {j + 1} saved successfully")

            else:
                print(f"Event {j + 1}: Trigger timeout")
                # 如果超时，重置示波器状态
                inst.write("*CLS")
                inst.write(":STOP")

        except KeyboardInterrupt:
            print("\nAcquisition interrupted by user")
            break
        except Exception as main_e:
            print(f"Main loop error: {main_e}")
            # 尝试复位状态
            inst.write("*CLS")
            inst.write(":STOP")
            time.sleep(1)

    print(f"\nAcquisition complete. {event_count} events saved to {outfile}")

    # 最后将示波器设置回运行状态
    inst.write(":RUN")

    # 关闭连接
    inst.close()


def simple_test(inst):
    """
    简单的测试函数，用于调试数据格式
    """
    try:
        # 测试获取IDN
        print("Testing connection...")
        idn = inst.query("*IDN?")
        print(f"IDN: {idn}")

        # 测试波形格式
        print("\nTesting waveform format...")
        format_resp = inst.query(":WAVeform:FORMat?")
        print(f"Current format: {format_resp}")

        # 设置为ASCII格式进行测试
        inst.write(":WAVeform:FORMat ASCii")

        # 获取前导信息
        preamble = inst.query(":WAVeform:PREamble?")
        print(f"Preamble: {preamble}")

        # 尝试读取少量数据
        inst.write(":WAVeform:SOURce CHANnel1")
        inst.write(":WAVeform:POINts 10")  # 只请求10个点

        # 读取数据
        raw_data = inst.query(":WAVeform:DATA?")
        print(f"\nRaw data (first 500 chars): {raw_data[:500]}")

        # 解析数据
        if raw_data.startswith("#"):
            print("\nData has TMC header")
            num_digits = int(raw_data[1])
            print(f"Number of length digits: {num_digits}")
            length_str = raw_data[2 : 2 + num_digits]
            print(f"Data length: {length_str}")
            data_part = raw_data[2 + num_digits :]
            print(f"Data sample: {data_part[:100]}")

    except Exception as e:
        print(f"Test error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # 先进行简单的连接测试
    inst = connect_to_scope()
    if inst != 0:
        try:
            # 运行测试
            simple_test(inst)

            # 询问是否开始采集
            response = input("\nDo you want to start data acquisition? (y/n): ")
            if response.lower() == "y":
                # 开始采集少量数据
                start_acquire(entries=1500, points=500)
            else:
                print("Test completed.")
        finally:
            inst.close()
