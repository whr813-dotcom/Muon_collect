import pandas as pd

THRESHOLD_V1 = -0.3  # Voltage1 阈值：筛选极小值 < THRESHOLD_V1 的Event
THRESHOLD_V2 = 1.0  # Voltage2 阈值：筛选峰高（max-min）> THRESHOLD_V2 的Event

input_file = (
    r"D:\科创\科创\曦源项目\3.27组会\程序化采集\agilent_data_2026-03-21-15-23-12.csv"
)
output_file = r"D:\科创\科创\曦源项目\3.27组会\程序化采集\filtered_voltage1.csv"

df = pd.read_csv(input_file)

event_v1_min = df.groupby("Event")["Voltage1"].min()
event_v2_peak = df.groupby("Event")["Voltage2"].apply(lambda x: x.max() - x.min())

v1_qualified = event_v1_min[event_v1_min < THRESHOLD_V1].index
v2_qualified = event_v2_peak[event_v2_peak > THRESHOLD_V2].index

qualified_events = v1_qualified.intersection(v2_qualified)

filtered = df[df["Event"].isin(qualified_events)][["Event", "Voltage1", "Voltage2"]]

filtered.to_csv(output_file, index=False)

print(
    f"满足 Voltage1 极小值 < {THRESHOLD_V1}V 且 Voltage2 峰高 > {THRESHOLD_V2}V 的Event数: {len(qualified_events)}"
)
print(f"总数据条数: {len(filtered)}")
print(filtered.head(20))
