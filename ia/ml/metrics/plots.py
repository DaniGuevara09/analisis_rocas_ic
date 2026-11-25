"""Gráficas de curvas ROC y Precisión-Recall comparando modelos."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = {"YOLOv11m-seg": "#2a78d6", "U-Net": "#e07b22", "MobileSAM": "#3a9a5b",
          "HDBSCAN": "#8a8a8a", "YOLO+U-Net bordes": "#7b4fc9", "U-Net semántica": "#c94f7b"}


def plot_roc(accumulators: dict, out_png, title="Curva ROC a nivel de píxel"):
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    for name, acc in accumulators.items():
        fpr, tpr, _ = acc.roc_curve()
        ax.plot(fpr, tpr, lw=2, color=COLORS.get(name), label=f"{name} (AUC = {acc.roc_auc():.3f})")
    ax.plot([0, 1], [0, 1], ls="--", lw=1, color="#bbbbbb", label="Azar (AUC = 0.5)")
    ax.set(xlim=(0, 1), ylim=(0, 1.01), xlabel="Tasa de falsos positivos (1 − especificidad)",
           ylabel="Tasa de verdaderos positivos (sensibilidad)", title=title)
    ax.grid(alpha=0.25); ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(out_png, dpi=160); plt.close(fig)


def plot_pr(accumulators: dict, out_png, title="Curva Precisión-Recall a nivel de píxel"):
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    for name, acc in accumulators.items():
        r, p = acc.pr_curve()
        ax.plot(r, p, lw=2, color=COLORS.get(name), label=f"{name} (AP = {acc.pr_auc():.3f})")
    ax.set(xlim=(0, 1), ylim=(0, 1.01), xlabel="Recall", ylabel="Precisión", title=title)
    ax.grid(alpha=0.25); ax.legend(loc="lower left", frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(out_png, dpi=160); plt.close(fig)


def plot_instance_pr(inst_accumulators: dict, out_png, iou_thr=0.5):
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    for name, acc in inst_accumulators.items():
        r, p = acc.pr_curve()
        ax.plot(r, p, lw=2, color=COLORS.get(name), label=f"{name} (AP@{iou_thr:.2f} = {acc.ap():.3f})")
    ax.set(xlim=(0, 1), ylim=(0, 1.01), xlabel="Recall (fragmentos)", ylabel="Precisión (fragmentos)",
           title=f"Curva PR por instancia (IoU ≥ {iou_thr})")
    ax.grid(alpha=0.25); ax.legend(loc="lower left", frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(out_png, dpi=160); plt.close(fig)
