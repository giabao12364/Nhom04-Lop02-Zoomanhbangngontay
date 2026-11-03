import csv
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_CSV = os.path.join(BASE_DIR, "zoom_log.csv")
LOG_PNG = os.path.join(BASE_DIR, "zoom_plot.png")


class ZoomLogger:
    def __init__(self):
        self.t0 = None
        self.rows = []

    def log(self, ratio, zoom_raw, zoom_smooth):
        now = time.time()
        if self.t0 is None:
            self.t0 = now
        self.rows.append((now - self.t0, ratio, zoom_raw, zoom_smooth))

    def save_csv(self, path=LOG_CSV):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["t", "ratio", "zoom_raw", "zoom_smooth"])
            writer.writerows(self.rows)
        return path


def plot_log(csv_path=LOG_CSV, out_png=LOG_PNG):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t, ratio, raw, smooth = [], [], [], []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t.append(float(row["t"]))
            ratio.append(float(row["ratio"]))
            raw.append(float(row["zoom_raw"]))
            smooth.append(float(row["zoom_smooth"]))

    if not t:
        print("[LOI] File log rong, chua co du lieu zoom.")
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)

    ax1.plot(t, raw, color="#e64553", linewidth=1.0, alpha=0.7, label="Zoom tho (truoc lam muot)")
    ax1.plot(t, smooth, color="#1e66f5", linewidth=2.2, label="Zoom da lam muot (bo loc)")
    ax1.set_ylabel("Muc zoom (x)")
    ax1.set_title("So sanh muc zoom: truoc va sau khi lam muot")
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2.plot(t, ratio, color="#40a02b", linewidth=1.0)
    ax2.set_xlabel("Thoi gian (s)")
    ax2.set_ylabel("ratio = distance / palm")
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)
    return out_png


if __name__ == "__main__":
    if os.path.exists(LOG_CSV):
        print("[OK] Da ve lai bieu do:", plot_log())
    else:
        print("[LOI] Chua co file log:", LOG_CSV)
