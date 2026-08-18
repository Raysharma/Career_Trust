"""
Trains the baseline XGBoost classifier on the fake job postings dataset.
Combines TF-IDF features with numeric heuristics and saves the resulting model.
"""

import os
import sys
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score, classification_report
from scipy.sparse import hstack, csr_matrix
from xgboost import XGBClassifier
import joblib

# Fix Windows console encoding if run directly
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(project_root, 'fake_job_postings.csv')
    
    if not os.path.exists(csv_path):
        print(f"🚨 ERROR: Cannot find {csv_path}. Please make sure fake_job_postings.csv is in the project root.")
        return

    print("Loading dataset...")
    df = pd.read_csv(csv_path)
    df.fillna("", inplace=True)

    # Combine text columns
    df['text'] = (
        df['title'] + " " + df['description'] + " " + 
        df['company_profile'] + " " + df['requirements'] + " " + df['benefits']
    )

    # Simple numeric checks
    df['has_salary'] = (df['salary_range'] != "").astype(int)
    df['has_company_profile'] = (df['company_profile'] != "").astype(int)
    df['has_requirements'] = (df['requirements'] != "").astype(int)
    df['has_benefits'] = (df['benefits'] != "").astype(int)
    df['desc_word_count'] = df['description'].apply(lambda x: len(x.split()))

    numeric_cols = [
        'has_company_logo', 'has_questions', 'telecommuting',
        'has_salary', 'has_company_profile', 'has_requirements',
        'has_benefits', 'desc_word_count'
    ]

    # Split dataset
    X_text = df['text']
    X_numeric = df[numeric_cols]
    y = df['fraudulent']

    X_text_train, X_text_test, X_num_train, X_num_test, y_train, y_test = train_test_split(
        X_text, X_numeric, y, test_size=0.2, random_state=42, stratify=y
    )

    # TF-IDF Vectorizer
    print("Vectorizing text features...")
    vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), sublinear_tf=True)
    X_text_train_vec = vectorizer.fit_transform(X_text_train)
    X_text_test_vec = vectorizer.transform(X_text_test)

    # Horizontally stack vectorizer text and numeric features
    X_train = hstack([X_text_train_vec, csr_matrix(X_num_train.values)])
    X_test = hstack([X_text_test_vec, csr_matrix(X_num_test.values)])
    print(f"Combined features shape: {X_train.shape}")

    # Scale weight for imbalanced classes
    scale = (y_train == 0).sum() / (y_train == 1).sum()
    print(f"Class imbalance scale weight: {scale:.1f}")

    # XGBoost Model
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale,
        eval_metric='logloss',
        random_state=42,
        n_jobs=-1
    )

    print("\nTraining XGBoost model...")
    model.fit(X_train, y_train)

    # Evaluate
    pred = model.predict(X_test)
    f1 = f1_score(y_test, pred)
    print(f"\n🏆 XGBoost F1-Score: {f1*100:.2f}%")
    print(classification_report(y_test, pred, target_names=["Real Job", "Fake Job"]))

    # Save models in project root
    joblib.dump(model, os.path.join(project_root, 'model_v2.pkl'))
    joblib.dump(vectorizer, os.path.join(project_root, 'vectorizer_v2.pkl'))
    joblib.dump(numeric_cols, os.path.join(project_root, 'feature_cols_v2.pkl'))
    print("✅ Models saved: model_v2.pkl, vectorizer_v2.pkl, feature_cols_v2.pkl")

if __name__ == "__main__":
    main()
