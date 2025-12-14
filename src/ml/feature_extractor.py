import logging
from typing import Dict, List, Any
from datetime import datetime

class FeatureExtractor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_features(self, attack_data: Dict) -> List[float]:
        """Extract features for ML classification from attack data"""
        try:
            # Default feature values
            features = {
                'packet_rate': 1.0,
                'bandwidth': 10.0,
                'duration': 60.0,
                'unique_ips': 5,
                'protocol_count': 2,
                'request_size': 500.0
            }
            
            # Extract based on data source
            if attack_data.get('source') == 'abuseipdb':
                features.update(self._extract_from_abuseipdb(attack_data))
            elif attack_data.get('source') in ['cloudflare_public', 'cloudflare_insights', 'supplemental']:
                features.update(self._extract_from_synthetic(attack_data))
            else:
                features.update(self._extract_generic(attack_data))
            
            # Convert to list in the correct order expected by the model
            return [
                features['packet_rate'],
                features['bandwidth'], 
                features['duration'],
                features['unique_ips'],
                features['protocol_count'],
                features['request_size']
            ]
            
        except Exception as e:
            self.logger.warning(f"Error extracting features: {e}")
            # Return default features
            return [1.0, 10.0, 60.0, 5.0, 2.0, 500.0]
    
    def _extract_from_abuseipdb(self, attack_data: Dict) -> Dict[str, float]:
        """Extract features from AbuseIPDB data"""
        features = {}
        
        # Use abuse confidence and reports to estimate features
        confidence = attack_data.get('abuse_confidence', 50)
        total_reports = attack_data.get('total_reports', 1)
        attack_type = attack_data.get('attack_type', '').lower()
        
        # Scale features based on confidence and reports
        report_factor = min(total_reports / 10.0, 10.0)
        confidence_factor = confidence / 100.0
        
        if 'ddos' in attack_type:
            features.update({
                'packet_rate': 100 * report_factor * confidence_factor,
                'bandwidth': 1000 * report_factor * confidence_factor,
                'duration': 300,  # DDoS attacks are typically longer
                'unique_ips': 1000 * report_factor,
                'protocol_count': 4,
                'request_size': 1500.0
            })
        elif 'brute' in attack_type:
            features.update({
                'packet_rate': 50 * report_factor * confidence_factor,
                'bandwidth': 200 * report_factor * confidence_factor,
                'duration': 600,  # Brute force attacks can be very long
                'unique_ips': 1,   # Usually from single IP
                'protocol_count': 2,
                'request_size': 100.0
            })
        elif 'port' in attack_type or 'scan' in attack_type:
            features.update({
                'packet_rate': 20 * report_factor,
                'bandwidth': 50 * report_factor,
                'duration': 120,
                'unique_ips': 1,   # Usually from single IP
                'protocol_count': 1,
                'request_size': 64.0  # Small packets for scanning
            })
        else:
            # Generic attack
            features.update({
                'packet_rate': 30 * report_factor * confidence_factor,
                'bandwidth': 150 * report_factor * confidence_factor,
                'duration': 180,
                'unique_ips': 10 * report_factor,
                'protocol_count': 3,
                'request_size': 800.0
            })
        
        return features
    
    def _extract_from_synthetic(self, attack_data: Dict) -> Dict[str, float]:
        """Extract features from synthetic/insight data"""
        attack_type = attack_data.get('attack_type', '').lower()
        magnitude = attack_data.get('magnitude', 50)
        confidence = attack_data.get('confidence', 0.7)
        
        # Base features scaled by magnitude and confidence
        base_scale = magnitude / 50.0 * confidence
        
        if 'ddos' in attack_type:
            return {
                'packet_rate': 500 * base_scale,
                'bandwidth': 2000 * base_scale,
                'duration': 300,
                'unique_ips': 5000 * base_scale,
                'protocol_count': 5,
                'request_size': 1200.0
            }
        elif 'brute' in attack_type:
            return {
                'packet_rate': 100 * base_scale,
                'bandwidth': 300 * base_scale,
                'duration': 600,
                'unique_ips': 10 * base_scale,
                'protocol_count': 3,
                'request_size': 200.0
            }
        elif 'port' in attack_type or 'scan' in attack_type:
            return {
                'packet_rate': 50 * base_scale,
                'bandwidth': 100 * base_scale,
                'duration': 180,
                'unique_ips': 5 * base_scale,
                'protocol_count': 2,
                'request_size': 64.0
            }
        elif 'web' in attack_type:
            return {
                'packet_rate': 80 * base_scale,
                'bandwidth': 400 * base_scale,
                'duration': 120,
                'unique_ips': 100 * base_scale,
                'protocol_count': 4,
                'request_size': 800.0
            }
        else:
            # Generic attack
            return {
                'packet_rate': 150 * base_scale,
                'bandwidth': 600 * base_scale,
                'duration': 240,
                'unique_ips': 200 * base_scale,
                'protocol_count': 3,
                'request_size': 500.0
            }
    
    def _extract_generic(self, attack_data: Dict) -> Dict[str, float]:
        """Extract features from generic attack data"""
        magnitude = attack_data.get('magnitude', 50)
        confidence = attack_data.get('confidence', 0.7)
        
        scale = magnitude / 50.0 * confidence
        
        return {
            'packet_rate': 100 * scale,
            'bandwidth': 500 * scale,
            'duration': 180,
            'unique_ips': 100 * scale,
            'protocol_count': 3,
            'request_size': 600.0
        }
    
    def extract_from_cloudflare(self, attack_data: Dict) -> Dict[str, Any]:
        """Legacy method - now handled by extract_features"""
        return self._extract_from_synthetic(attack_data)
    
    def extract_from_abuseipdb(self, attack_data: Dict) -> Dict[str, Any]:
        """Legacy method - now handled by extract_features"""
        return self._extract_from_abuseipdb(attack_data)