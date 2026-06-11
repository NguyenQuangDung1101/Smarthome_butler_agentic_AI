import matplotlib.pyplot as plt

# Data
shots = [0, 1, 2, 3, 4]
deterministic_eval = [73.22, 75.00, 76.89, 78.56, 79.78]
llm_judge = [74.56, 76.00, 76.78, 79.78, 81.22]

# Plot
plt.figure(figsize=(8.5, 5.2))

plt.plot(
    shots,
    deterministic_eval,
    marker='o',
    markersize=7,
    linewidth=2.2,
    color='#1f77b4',   # blue
    label='Deterministic Evaluation'
)

plt.plot(
    shots,
    llm_judge,
    marker='s',
    markersize=7,
    linewidth=2.2,
    color='#d62728',   # red
    label='LLM-as-a-Judge Evaluation'
)

# Labels and title
plt.xlabel('Number of In-Context Examples', fontsize=12)
plt.ylabel('Evaluation Accuracy (%)', fontsize=12)
plt.title(
    '',
    fontsize=14,
    fontweight='bold',
    pad=14
)

# X-axis ticks
plt.xticks(
    shots,
    ['0-shot', '1-shot', '2-shot', '3-shot', '4-shot'],
    fontsize=11
)
plt.yticks(fontsize=11)

# Thin grid
plt.grid(
    True,
    linestyle='--',
    linewidth=0.5,
    alpha=0.35
)

# Legend
plt.legend(
    fontsize=11,
    frameon=True,
    edgecolor='gray'
)

# Optional: make borders cleaner
ax = plt.gca()
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Layout
plt.tight_layout()

# Save figure
plt.savefig(
    'few_shot_ablation_study.png',
    dpi=300,
    bbox_inches='tight'
)

plt.show()