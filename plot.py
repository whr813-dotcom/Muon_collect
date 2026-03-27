import pandas as pd
import matplotlib.pyplot as plt

csv_file = "agilent_data_2026-03-13-16-03-48.csv"
event_num = int(input("Enter Event number: "))
time_window = 0.01  # 时间窗口范围（秒），只显示 0 附近的数据

df = pd.read_csv(csv_file)
event_data = df[df["Event"] == event_num]

if event_data.empty:
    print(f"Event {event_num} not found")
    exit()

event_data = event_data[
    (event_data["Time"] >= -time_window) & (event_data["Time"] <= time_window)
]

plt.figure(figsize=(10, 6))
plt.plot(
    event_data["Time"],
    event_data["Voltage1"] * 5,
    label="Channel 1 (x5 )",
    linewidth=1,
)
plt.plot(event_data["Time"], event_data["Voltage2"], label="Channel 2", linewidth=1)

plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.title(f"Event {event_num}")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
