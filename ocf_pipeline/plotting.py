import matplotlib.pyplot as plt
import pandas as pd


def plot_generation(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots()
    for psr in df.psr_type.unique():
        subset = df[df.psr_type == psr]
        ax.plot(subset.start_time, subset.quantity, label=psr)
    ax.set_xlabel("Time")
    ax.set_ylabel("MW")
    ax.legend()
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show() 