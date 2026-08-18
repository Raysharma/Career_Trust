"""
Fine-tunes the DistilBERT transformer model on a balanced subset or the full job postings dataset.
Saves checkpoints and the finalized classifier weights to the fraud_job_model folder.
"""

import os
import sys
import pandas as pd
import numpy as np
import torch
import torch.nn as nn

# Fix Windows console encoding if run directly
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from datasets import Dataset
    from transformers import (
        AutoTokenizer, 
        AutoModelForSequenceClassification, 
        TrainingArguments, 
        Trainer
    )
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support
    from sklearn.model_selection import train_test_split
except ImportError:
    print("🚨 ERROR: Missing libraries! Run: pip install torch transformers datasets scikit-learn")
    sys.exit(1)

# Configuration
USE_SMALL_DATASET = True
MODEL_NAME = "distilbert-base-uncased"
MAX_LENGTH = 256
EPOCHS = 4

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(project_root, 'fake_job_postings.csv')
    output_dir = os.path.join(project_root, 'fraud_job_model')
    
    if not os.path.exists(csv_path):
        print(f"🚨 ERROR: Cannot find {csv_path}. Please make sure fake_job_postings.csv is in the project root.")
        return

    print("=" * 60)
    print("🏋️  FINE-TUNING DISTILBERT")
    print("=" * 60)

    print("Loading data...")
    df = pd.read_csv(csv_path)
    df.fillna('', inplace=True)
    df['text'] = df['title'] + " " + df['company_profile'] + " " + df['description'] + " " + df['requirements'] + " " + df['benefits']
    df = df[['text', 'fraudulent']].rename(columns={'fraudulent': 'label'})

    if USE_SMALL_DATASET:
        # Use 250 real and 250 fake to balance classes
        fake_jobs = df[df['label'] == 1].sample(250, random_state=42)
        real_jobs = df[df['label'] == 0].sample(250, random_state=42)
        df = pd.concat([real_jobs, fake_jobs]).sample(frac=1, random_state=42)
        print(f"⚠️ Using balanced subset: {len(real_jobs)} real + {len(fake_jobs)} fake = {len(df)} total")
    else:
        print("🚀 Using FULL dataset! This will take a long time.")

    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['label'])

    train_dataset = Dataset.from_pandas(train_df)
    test_dataset = Dataset.from_pandas(test_df)

    print("\nTokenizing data...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    def tokenize_func(examples):
        return tokenizer(examples['text'], padding="max_length", truncation=True, max_length=MAX_LENGTH)

    train_tokenized = train_dataset.map(tokenize_func, batched=True)
    test_tokenized = test_dataset.map(tokenize_func, batched=True)

    def compute_metrics(eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)
        precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average='binary', zero_division=0)
        acc = accuracy_score(labels, predictions)
        return {
            'accuracy': acc,
            'f1': f1,
            'precision': precision,
            'recall': recall
        }

    print(f"\nLoading {MODEL_NAME} model for classification...")
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
    model.config.id2label = {0: "REAL", 1: "FRAUD"}
    model.config.label2id = {"REAL": 0, "FRAUD": 1}

    # Class weights for imbalanced calculation
    label_counts = train_df['label'].value_counts().sort_index()
    total = len(train_df)
    class_weights = torch.tensor(
        [total / (2 * label_counts[0]), total / (2 * label_counts[1])],
        dtype=torch.float32
    )
    print(f"Class weights: Real={class_weights[0]:.2f}, Fake={class_weights[1]:.2f}")

    # Custom Weighted Loss Trainer
    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            logits = outputs.logits
            loss_fn = nn.CrossEntropyLoss(weight=class_weights.to(logits.device))
            loss = loss_fn(logits, labels)
            return (loss, outputs) if return_outputs else loss

    training_args = TrainingArguments(
        output_dir=output_dir,
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        num_train_epochs=EPOCHS,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
    )

    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=test_tokenized,
        compute_metrics=compute_metrics,
    )

    print("\n" + "=" * 60)
    print("🚀 STARTING TRAINING! (This may take some time...)")
    print("=" * 60)
    trainer.train()

    print("\n" + "=" * 60)
    print("📊 FINAL EVALUATION")
    print("=" * 60)
    eval_results = trainer.evaluate()
    for key, val in eval_results.items():
        if key.startswith("eval_"):
            print(f"   {key.replace('eval_', '').capitalize():>12}: {val:.4f}")

    final_model_dir = os.path.join(output_dir, 'final_model')
    print(f"\nSaving final model to {final_model_dir}...")
    trainer.save_model(final_model_dir)
    tokenizer.save_pretrained(final_model_dir)

    print(f"\n✅ Training complete! Model saved to {final_model_dir}")

if __name__ == "__main__":
    main()
