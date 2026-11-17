"""Train the experimental GreenLedger character-ngram line-role model on train only."""

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from greenledger.ai_field_extraction import (  # noqa: E402
    CLASS_LABELS,
    DEFAULT_MODEL_PATH,
    FEATURE_BUCKETS,
    NGRAM_RANGE,
    char_ngram_features,
    load_training_lines,
)


SEED = 20261110
EPOCHS = 40
LEARNING_RATE = 0.04


def train(output_path=DEFAULT_MODEL_PATH):
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(1)

    samples, counts = load_training_lines(ROOT)
    label_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    row_indices = []
    column_indices = []
    feature_values = []
    targets = []
    for row_index, (line, label, _document_id) in enumerate(samples):
        for column_index, value in char_ngram_features(line):
            row_indices.append(row_index)
            column_indices.append(column_index)
            feature_values.append(value)
        targets.append(label_to_index[label])

    features = torch.sparse_coo_tensor(
        torch.tensor([row_indices, column_indices], dtype=torch.long),
        torch.tensor(feature_values, dtype=torch.float32),
        (len(samples), FEATURE_BUCKETS),
    ).coalesce()
    target_tensor = torch.tensor(targets, dtype=torch.long)
    class_counts = torch.bincount(target_tensor, minlength=len(CLASS_LABELS)).float()
    class_weights = torch.where(class_counts > 0, class_counts.rsqrt(), torch.zeros_like(class_counts))
    class_weights = class_weights / class_weights.mean()

    weight = torch.nn.Parameter(torch.zeros(FEATURE_BUCKETS, len(CLASS_LABELS)))
    bias = torch.nn.Parameter(torch.zeros(len(CLASS_LABELS)))
    optimizer = torch.optim.Adam((weight, bias), lr=LEARNING_RATE, weight_decay=1e-4)
    final_loss = None
    for _epoch in range(EPOCHS):
        optimizer.zero_grad(set_to_none=True)
        logits = torch.sparse.mm(features, weight) + bias
        loss = F.cross_entropy(logits, target_tensor, weight=class_weights)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach())

    artifact = {
        "model_id": "greenledger_char_ngram_line_role_v1",
        "method": "supervised character n-gram hashed linear classifier",
        "training_split": "train",
        "training_documents": counts["documents"],
        "training_lines": counts["lines"],
        "positive_field_lines": counts["positive_lines"],
        "labels": list(CLASS_LABELS),
        "feature_buckets": FEATURE_BUCKETS,
        "ngram_range": list(NGRAM_RANGE),
        "seed": SEED,
        "epochs": EPOCHS,
        "learning_rate": LEARNING_RATE,
        "final_training_loss": final_loss,
        "class_counts": {label: int(class_counts[index]) for index, label in enumerate(CLASS_LABELS)},
        "bias": bias.detach().cpu().tolist(),
        "weights": weight.detach().cpu().T.contiguous().tolist(),
        "confidence_calibrated": False,
        "scope_factor_or_co2e_outputs": False,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "TRAINED_CANDIDATE",
        "output": str(output_path),
        "training_split": "train",
        "training_documents": counts["documents"],
        "training_lines": counts["lines"],
        "positive_field_lines": counts["positive_lines"],
        "class_counts": artifact["class_counts"],
        "epochs": EPOCHS,
        "final_training_loss": final_loss,
        "validation_used_for_training_or_tuning": False,
        "test_split_loaded": False,
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_MODEL_PATH)
    args = parser.parse_args()
    train(args.output)


if __name__ == "__main__":
    main()
