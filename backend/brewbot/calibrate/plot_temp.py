import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    file_paths = ["recordings/rec_2024-10-20T16-14-16.txt", "recordings/rec_2024-10-20T18-15-37.txt", "recordings/rec_2024-10-20T20-15-19.txt"]

    data = []
    for file_path in file_paths:
        with open(file_path) as f:
            data.extend([json.loads(line.replace("Z", "")) for line in f])

    df = pd.DataFrame(data)
    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df = df.astype({"real_temp_c": "float64", "can_temp_v": "float64"})
    df = df.set_index("time")

    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Plot real_temp_c on the left y-axis
    ax1.plot(df.index, df['real_temp_c'], color='blue', label='Real Temp (C)')
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Real Temp (C)', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')

    # Create a second y-axis for can_temp_v
    ax2 = ax1.twinx()
    ax2.plot(df.index, df['can_temp_v'], color='red', label='CAN Temp (V)')
    ax2.set_ylabel('CAN Temp (V)', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    plt.xticks(rotation=45)

    plt.title('Temperature Data Over Time')

    plt.tight_layout()
    plt.savefig('temp_plot.png')


if __name__ == "__main__":
    main()
