import pandas as pd

THRESHOLD_V2 = -0.08  # Voltage2 阈值：筛选极小值 < THRESHOLD_V2 的Event
THRESHOLD_V1 = 0.04   # Voltage1 阈值：筛选峰高（max-min）> THRESHOLD_V1 的Event

input_file = (
    r"D:\科创\科创\曦源项目\3.27组会\程序化采集\agilent_data_2026-03-13-16-03-48.csv"
)
output_file = r"D:\科创\科创\曦源项目\3.27组会\程序化采集\filtered_voltage1.csv"

df = pd.read_csv(input_file)

event_v2_min = df.groupby("Event")["Voltage2"].min()
event_v1_peak = df.groupby("Event")["Voltage1"].apply(lambda x: x.max() - x.min())

v2_qualified = event_v2_min[event_v2_min < THRESHOLD_V2].index
v1_qualified = event_v1_peak[event_v1_peak > THRESHOLD_V1].index

qualified_events = v1_qualified.intersection(v2_qualified)

filtered = df[df["Event"].isin(qualified_events)][["Event", "Voltage1", "Voltage2"]]

filtered.to_csv(output_file, index=False)

print(
    f"满足 Voltage2 极小值 < {THRESHOLD_V2}V 且 Voltage1 峰高 > {THRESHOLD_V1}V 的Event数: {len(qualified_events)}"
)
print(f"总数据条数: {len(filtered)}")
print(filtered.head(20))
