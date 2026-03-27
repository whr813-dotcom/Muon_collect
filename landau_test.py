import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import sys

input_file = r"D:\科创\科创\曦源项目\3.27组会\程序化采集\v2_peaks.csv"
output_file = r"D:\科创\科创\曦源项目\3.27组会\程序化采集\landau_fit.png"
column_name = "Voltage2_Peak_Abs"

df = pd.read_csv(input_file)
data = df[column_name].values

loc, scale = stats.landau.fit(data)
print(f"Landau fit params: loc={loc:.4f}, scale={scale:.4f}")

ks_stat, p_value = stats.kstest(data, "landau", args=(loc, scale))
print(f"KS test: statistic={ks_stat:.4f}, p-value={p_value:.4f}")

if p_value > 0.05:
    print("结论: 数据满足朗道分布 (p > 0.05)")
else:
    print("结论: 数据不满足朗道分布 (p <= 0.05)")

plt.figure(figsize=(10, 6))
plt.hist(data, bins=30, density=True, alpha=0.7, label="Data")
x = np.linspace(data.min(), data.max(), 200)
pdf = stats.landau.pdf(x, loc, scale)
plt.plot(x, pdf, "r-", lw=2, label="Landau fit")

mpv = loc
plt.axvline(mpv, color="g", linestyle="--", label=f"MPV = {mpv:.4f}")

plt.xlabel("Voltage Peak (V)")
plt.ylabel("Probability Density")
plt.title(f"Landau Distribution Fit\nKS p-value = {p_value:.4f}")
plt.legend()
plt.grid(True)
plt.savefig(output_file)
plt.show()

print(f"图像已保存到: {output_file}")
