import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
import os
import logging
from typing import List, Optional
import json

class DDOSClassifier:
    def __init__(self, model_path: str = "models/ddos_classifier.joblib"):
        self.model_path = model_path
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = [
            'packet_rate', 'bandwidth', 'duration', 
            'unique_ips', 'protocol_count', 'request_size'
        ]
        self.load_or_train_model()
    
    def load_or_train_model(self):
        """Load existing model or train a new one"""
        if os.path.exists(self.model_path):
            try:
                # Try to load the model data
                loaded_data = joblib.load(self.model_path)
                
                if isinstance(loaded_data, dict):
                    # New format with model and scaler
                    self.model = loaded_data.get('model')
                    self.scaler = loaded_data.get('scaler')
                    self.feature_names = loaded_data.get('feature_names', self.feature_names)
                    
                    if self.model is not None and self.scaler is not None:
                        logging.info("✅ Loaded pre-trained DDoS classifier with scaler")
                        return
                    else:
                        logging.warning("Model data incomplete, retraining...")
                else:
                    # Old format, retrain
                    logging.warning("Old model format detected, retraining...")
                    
            except Exception as e:
                logging.error(f"Error loading model: {e}. Training new model...")
        
        # Train new model if loading failed
        logging.info("No pre-trained model found. Training new model...")
        self.train_default_model()

    def train_default_model(self):
        """Train a default model with synthetic data"""
        np.random.seed(42)
        n_samples = 2000
        
        # Generate synthetic training data
        X_normal = np.column_stack([
            np.random.exponential(1, n_samples//2),      # packet_rate
            np.random.exponential(10, n_samples//2),     # bandwidth
            np.random.exponential(60, n_samples//2),     # duration
            np.random.poisson(5, n_samples//2),          # unique_ips
            np.random.randint(1, 4, n_samples//2),       # protocol_count
            np.random.normal(500, 100, n_samples//2)     # request_size
        ])
        
        X_attack = np.column_stack([
            np.random.exponential(100, n_samples//2),    # packet_rate
            np.random.exponential(1000, n_samples//2),   # bandwidth
            np.random.exponential(300, n_samples//2),    # duration
            np.random.poisson(1000, n_samples//2),       # unique_ips
            np.random.randint(1, 8, n_samples//2),       # protocol_count
            np.random.normal(1500, 500, n_samples//2)    # request_size
        ])
        
        X = np.vstack([X_normal, X_attack])
        y = np.hstack([np.zeros(n_samples//2), np.ones(n_samples//2)])
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            class_weight='balanced'
        )
        
        self.model.fit(X_scaled, y)
        
        # Save both model and scaler
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names
        }
        
        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(model_data, self.model_path)
        logging.info(f"✅ Model trained and saved to {self.model_path}")

    def predict(self, features: List[float]) -> float:
        """Predict DDoS probability for given features"""
        if self.model is None or self.scaler is None:
            logging.error("Model or scaler not initialized")
            return 0.5  # Return neutral confidence
        
        try:
            features_array = np.array(features).reshape(1, -1)
            features_scaled = self.scaler.transform(features_array)
            probability = self.model.predict_proba(features_scaled)[0][1]
            return float(probability)
        except Exception as e:
            logging.error(f"Prediction error: {e}")
            # Fallback: simple rule-based confidence
            packet_rate = features[0] if len(features) > 0 else 1.0
            if packet_rate > 50:
                return 0.8
            elif packet_rate > 20:
                return 0.6
            else:
                return 0.3
        
    def extract_features_from_attack(self, attack_data: dict) -> List[float]:
            """Extract features from attack data for prediction"""
            # Default values
            features = [1.0, 10.0, 60.0, 5.0, 2.0, 500.0]
            
            try:
                metadata = attack_data.get('metadata', {})
                
                # Map attack data to features
                feature_mapping = {
                    'packet_rate': metadata.get('packet_rate', 1.0),
                    'bandwidth': attack_data.get('magnitude', 10.0) * 10,
                    'duration': metadata.get('duration', 60.0),
                    'unique_ips': metadata.get('unique_source_ips', 5),
                    'protocol_count': metadata.get('protocol_count', 2),
                    'request_size': metadata.get('avg_request_size', 500.0)
                }
                
                # Update features with actual data
                for i, feature_name in enumerate(self.feature_names):
                    if feature_name in feature_mapping:
                        features[i] = feature_mapping[feature_name]
                
            except Exception as e:
                logging.warning(f"Error extracting features: {e}")
            
            return features
        
    def get_feature_importance(self) -> dict:
            """Get feature importance scores"""
            if self.model is None:
                return {}
            
            importance_scores = self.model.feature_importances_
            return dict(zip(self.feature_names, importance_scores))