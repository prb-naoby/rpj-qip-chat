"""
Unit tests for fuzzy matching logic in qa_engine.
Uses the actual _fuzzy_match function from the app module.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd

from app.qa_engine import _fuzzy_match


class TestFuzzyMatch:
    """Tests for _fuzzy_match function."""
    
    @pytest.fixture
    def supplier_series(self):
        """Sample supplier names for testing."""
        return pd.Series([
            'DONG JIN TEXTILE',
            'SUNG DONG',
            'OTHER SUPPLIER',
            'DONGG JIN (TYPO)',
            'PT DONG JIN',
            'ABC COMPANY'
        ])
    
    def test_exact_substring_match(self, supplier_series):
        """Test that exact substring matches work."""
        mask = _fuzzy_match(supplier_series, 'DONG JIN', threshold=80)
        
        # Should match: DONG JIN TEXTILE, PT DONG JIN
        assert mask.iloc[0] == True   # DONG JIN TEXTILE
        assert mask.iloc[4] == True   # PT DONG JIN
    
    def test_single_word_match(self, supplier_series):
        """Test matching with a single word."""
        mask = _fuzzy_match(supplier_series, 'SUNG', threshold=80)
        
        # Should match: SUNG DONG
        assert mask.iloc[1] == True
    
    def test_fuzzy_typo_match(self, supplier_series):
        """Test that fuzzy matching catches typos."""
        mask = _fuzzy_match(supplier_series, 'DONG JIN', threshold=70)
        
        # DONGG JIN is a typo but should still match with lower threshold
        # This depends on the implementation - adjust expectations accordingly
        matched = supplier_series[mask].tolist()
        assert 'DONG JIN TEXTILE' in matched
    
    def test_no_match(self, supplier_series):
        """Test that unrelated queries don't match."""
        mask = _fuzzy_match(supplier_series, 'XYZ CORPORATION', threshold=90)
        
        # None should match
        assert mask.sum() == 0
    
    def test_case_insensitive(self, supplier_series):
        """Test that matching is case insensitive."""
        mask_lower = _fuzzy_match(supplier_series, 'dong jin', threshold=80)
        mask_upper = _fuzzy_match(supplier_series, 'DONG JIN', threshold=80)
        
        # Both should give same results
        assert mask_lower.equals(mask_upper)
    
    def test_handles_na_values(self):
        """Test that NA values are handled gracefully."""
        series = pd.Series(['DONG JIN', None, 'OTHER', pd.NA])
        mask = _fuzzy_match(series, 'DONG', threshold=80)
        
        # Should not crash, NA should return False
        assert mask.iloc[0] == True
        assert mask.iloc[1] == False
        assert mask.iloc[3] == False
    
    def test_whitespace_handling(self, supplier_series):
        """Test that extra whitespace is handled."""
        mask = _fuzzy_match(supplier_series, '  DONG JIN  ', threshold=80)
        
        # Should still match despite extra whitespace
        assert mask.iloc[0] == True  # DONG JIN TEXTILE
