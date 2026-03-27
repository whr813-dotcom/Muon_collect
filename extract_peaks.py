import pandas as pd

input_file = r"D:\科创\科创\曦源项目\3.27组会\程序化采集\filtered_voltage1.csv"
output_file = r"D:\科创\科创\曦源项目\3.27组会\程序化采集\v2_peaks.csv"

df = pd.read_csv(input_file)
event_peaks = df.groupby("Event")["Voltage2"].apply(lambda x: abs(x).max())

event_peaks.to_csv(output_file, header=["Voltage2_Peak_Abs"])
print(f"共 {len(event_peaks)} 个Event的峰值绝对值")
print(event_peaks.head(20))
