"""
Finance Enricher - Parse and analyze financial documents and statements
"""
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


@dataclass
class ParsedTransaction:
    """A parsed financial transaction"""
    date: Optional[datetime] = None
    description: str = ""
    amount: Optional[Decimal] = None
    transaction_type: Optional[str] = None  # debit, credit, transfer
    category: Optional[str] = None
    merchant: Optional[str] = None
    account: Optional[str] = None
    currency: str = "USD"
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'date': self.date.isoformat() if self.date else None,
            'description': self.description,
            'amount': str(self.amount) if self.amount else None,
            'transaction_type': self.transaction_type,
            'category': self.category,
            'merchant': self.merchant,
            'account': self.account,
            'currency': self.currency,
            'confidence': self.confidence
        }


@dataclass
class FinancialSummary:
    """Summary of financial document analysis"""
    total_transactions: int = 0
    total_credits: Decimal = Decimal('0')
    total_debits: Decimal = Decimal('0')
    net_balance: Decimal = Decimal('0')
    date_range: Tuple[Optional[datetime], Optional[datetime]] = (None, None)
    top_categories: List[Tuple[str, Decimal]] = None
    top_merchants: List[Tuple[str, int]] = None
    account_summary: Dict[str, Decimal] = None
    
    def __post_init__(self):
        if self.top_categories is None:
            self.top_categories = []
        if self.top_merchants is None:
            self.top_merchants = []
        if self.account_summary is None:
            self.account_summary = {}


class FinanceEnricher:
    """Analyzes and enriches financial documents and statements"""
    
    def __init__(self):
        # Common patterns for financial data extraction
        self.patterns = {
            # Date patterns
            'date': re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}'),
            
            # Amount patterns (various currencies)
            'amount': re.compile(r'[+-]?\$?[\d,]+\.?\d{0,2}|\$[\d,]+|\([\d,]+\.?\d{0,2}\)'),
            
            # Transaction descriptions
            'transaction_line': re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,.-]+|\([^)]+\))'),
            
            # Common financial institutions
            'bank_headers': re.compile(r'(Chase|Bank of America|Wells Fargo|Citi|Capital One|American Express|Discover)', re.IGNORECASE),
            
            # Account numbers
            'account_number': re.compile(r'Account.*?(\d{4,}|\*+\d{4})'),
            
            # Statement periods
            'statement_period': re.compile(r'Statement Period:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|through|-)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', re.IGNORECASE),
        }
        
        # Transaction categories based on common merchant patterns
        self.category_patterns = {
            'food': ['restaurant', 'cafe', 'pizza', 'mcdonald', 'starbucks', 'grocery', 'market', 'deli', 'bakery'],
            'gas': ['shell', 'exxon', 'bp', 'chevron', 'mobil', 'gas station', 'fuel'],
            'retail': ['amazon', 'target', 'walmart', 'costco', 'home depot', 'lowes', 'best buy'],
            'utilities': ['electric', 'gas company', 'water', 'internet', 'phone', 'cable'],
            'transportation': ['uber', 'lyft', 'taxi', 'metro', 'transit', 'parking', 'toll'],
            'healthcare': ['pharmacy', 'medical', 'hospital', 'doctor', 'clinic', 'dental'],
            'entertainment': ['netflix', 'spotify', 'movie', 'theater', 'gym', 'fitness'],
            'finance': ['bank', 'atm', 'fee', 'interest', 'transfer', 'payment', 'deposit']
        }
        
        logger.info("💰 Finance enricher initialized")
    
    async def parse_statement(self, text: str, source_path: Optional[str] = None) -> Tuple[List[ParsedTransaction], FinancialSummary]:
        """Parse financial statement text and extract transactions"""
        
        if not text or not text.strip():
            return [], FinancialSummary()
        
        transactions = []
        
        # Try different parsing approaches
        transactions.extend(self._parse_csv_format(text))
        transactions.extend(self._parse_statement_format(text))
        transactions.extend(self._parse_simple_format(text))
        
        # Remove duplicates based on date + description + amount
        unique_transactions = self._deduplicate_transactions(transactions)
        
        # Enhance transactions with categories
        for transaction in unique_transactions:
            if not transaction.category:
                transaction.category = self._categorize_transaction(transaction.description)
        
        # Generate summary
        summary = self._generate_financial_summary(unique_transactions)
        
        logger.info(f"Parsed {len(unique_transactions)} unique transactions from financial document")
        
        return unique_transactions, summary
    
    def _parse_csv_format(self, text: str) -> List[ParsedTransaction]:
        """Parse CSV-style financial data"""
        transactions = []
        
        lines = text.split('\n')
        
        # Look for CSV-like headers
        header_patterns = ['date', 'description', 'amount', 'balance']
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Check if this looks like a CSV header
            if any(pattern in line_lower for pattern in header_patterns):
                # Process subsequent lines as CSV data
                for data_line in lines[i+1:i+50]:  # Limit to avoid processing whole document
                    if not data_line.strip():
                        continue
                    
                    # Simple CSV parsing (comma or tab separated)
                    if ',' in data_line:
                        parts = data_line.split(',')
                    elif '\t' in data_line:
                        parts = data_line.split('\t')
                    else:
                        continue
                    
                    if len(parts) >= 3:
                        try:
                            transaction = self._parse_transaction_parts(parts)
                            if transaction:
                                transactions.append(transaction)
                        except:
                            continue
                
                break  # Only process first CSV-like section
        
        return transactions
    
    def _parse_statement_format(self, text: str) -> List[ParsedTransaction]:
        """Parse traditional bank statement format"""
        transactions = []
        
        # Look for transaction-like lines
        lines = text.split('\n')
        
        for line in lines:
            match = self.patterns['transaction_line'].match(line.strip())
            if match:
                date_str, description, amount_str = match.groups()
                
                try:
                    transaction = ParsedTransaction()
                    
                    # Parse date
                    transaction.date = self._parse_date(date_str)
                    
                    # Clean description
                    transaction.description = description.strip()
                    
                    # Parse amount
                    transaction.amount, transaction.transaction_type = self._parse_amount(amount_str)
                    
                    if transaction.date and transaction.amount:
                        transaction.confidence = 0.8
                        transactions.append(transaction)
                        
                except Exception as e:
                    logger.debug(f"Failed to parse transaction line: {e}")
                    continue
        
        return transactions
    
    def _parse_simple_format(self, text: str) -> List[ParsedTransaction]:
        """Parse simple text format with date/description/amount patterns"""
        transactions = []
        
        # Find all amounts in the text
        amount_matches = list(self.patterns['amount'].finditer(text))
        date_matches = list(self.patterns['date'].finditer(text))
        
        # For each amount, try to find nearby date and description
        for amount_match in amount_matches:
            amount_start = amount_match.start()
            amount_str = amount_match.group()
            
            # Look for date within 200 characters before amount
            best_date = None
            for date_match in date_matches:
                if date_match.start() < amount_start and amount_start - date_match.end() < 200:
                    best_date = date_match.group()
            
            if best_date:
                try:
                    transaction = ParsedTransaction()
                    
                    # Extract description (text between date and amount)
                    date_end = text.find(best_date) + len(best_date)
                    description = text[date_end:amount_start].strip()
                    
                    # Clean up description
                    description = re.sub(r'\s+', ' ', description)
                    if len(description) > 100:
                        description = description[:100] + "..."
                    
                    transaction.date = self._parse_date(best_date)
                    transaction.description = description
                    transaction.amount, transaction.transaction_type = self._parse_amount(amount_str)
                    
                    if transaction.date and transaction.amount and len(description) > 3:
                        transaction.confidence = 0.6
                        transactions.append(transaction)
                        
                except Exception:
                    continue
        
        return transactions
    
    def _parse_transaction_parts(self, parts: List[str]) -> Optional[ParsedTransaction]:
        """Parse transaction from CSV parts"""
        
        if len(parts) < 3:
            return None
        
        try:
            transaction = ParsedTransaction()
            
            # Try different column orders
            for i, part in enumerate(parts[:4]):  # Only check first 4 columns
                part = part.strip().strip('"')
                
                # Try to parse as date
                if not transaction.date:
                    try:
                        transaction.date = self._parse_date(part)
                        continue
                    except:
                        pass
                
                # Try to parse as amount
                if not transaction.amount:
                    try:
                        amount, trans_type = self._parse_amount(part)
                        if amount:
                            transaction.amount = amount
                            transaction.transaction_type = trans_type
                            continue
                    except:
                        pass
                
                # Otherwise treat as description
                if not transaction.description and len(part) > 2:
                    transaction.description = part
            
            # Must have at least date, amount, and description
            if transaction.date and transaction.amount and transaction.description:
                transaction.confidence = 0.9
                return transaction
                
        except Exception:
            pass
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats"""
        
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # Common date formats
        formats = [
            '%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y',
            '%Y-%m-%d', '%Y/%m/%d',
            '%b %d, %Y', '%B %d, %Y', '%b %d %Y', '%B %d %Y',
            '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _parse_amount(self, amount_str: str) -> Tuple[Optional[Decimal], Optional[str]]:
        """Parse amount and determine transaction type"""
        
        if not amount_str:
            return None, None
        
        # Clean the amount string
        amount_str = amount_str.strip()
        is_negative = False
        
        # Check for negative indicators
        if amount_str.startswith('-') or amount_str.startswith('('):
            is_negative = True
        
        # Remove currency symbols and formatting
        cleaned = re.sub(r'[^\d.,()-]', '', amount_str)
        cleaned = cleaned.strip('()')
        
        try:
            # Handle comma as thousands separator
            if ',' in cleaned and '.' in cleaned:
                # Both comma and period - assume comma is thousands separator
                cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                # Only comma - could be decimal separator in some locales
                # For now, assume it's thousands separator if more than 3 digits after
                parts = cleaned.split(',')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    cleaned = cleaned.replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            
            amount = Decimal(cleaned)
            
            if is_negative:
                amount = -amount
            
            # Determine transaction type
            if amount < 0:
                trans_type = 'debit'
            else:
                trans_type = 'credit'
            
            return abs(amount), trans_type
            
        except (InvalidOperation, ValueError):
            return None, None
    
    def _categorize_transaction(self, description: str) -> str:
        """Categorize transaction based on description"""
        
        if not description:
            return 'other'
        
        description_lower = description.lower()
        
        # Check category patterns
        for category, patterns in self.category_patterns.items():
            for pattern in patterns:
                if pattern.lower() in description_lower:
                    return category
        
        # Default fallback based on keywords
        if any(word in description_lower for word in ['atm', 'withdrawal', 'cash']):
            return 'cash'
        elif any(word in description_lower for word in ['deposit', 'payroll', 'salary']):
            return 'income'
        elif any(word in description_lower for word in ['fee', 'charge', 'penalty']):
            return 'fees'
        
        return 'other'
    
    def _deduplicate_transactions(self, transactions: List[ParsedTransaction]) -> List[ParsedTransaction]:
        """Remove duplicate transactions"""
        
        seen = set()
        unique = []
        
        for transaction in transactions:
            # Create key based on date, description prefix, and amount
            key_parts = [
                transaction.date.isoformat() if transaction.date else 'no_date',
                transaction.description[:50].lower().strip() if transaction.description else 'no_desc',
                str(transaction.amount) if transaction.amount else 'no_amount'
            ]
            key = '|'.join(key_parts)
            
            if key not in seen:
                seen.add(key)
                unique.append(transaction)
        
        return unique
    
    def _generate_financial_summary(self, transactions: List[ParsedTransaction]) -> FinancialSummary:
        """Generate summary statistics from transactions"""
        
        if not transactions:
            return FinancialSummary()
        
        summary = FinancialSummary()
        summary.total_transactions = len(transactions)
        
        # Calculate totals
        credits = Decimal('0')
        debits = Decimal('0')
        
        dates = []
        category_totals = {}
        merchant_counts = {}
        
        for transaction in transactions:
            if transaction.amount:
                if transaction.transaction_type == 'credit':
                    credits += transaction.amount
                else:
                    debits += transaction.amount
            
            if transaction.date:
                dates.append(transaction.date)
            
            if transaction.category:
                category_totals[transaction.category] = category_totals.get(transaction.category, Decimal('0')) + (transaction.amount or Decimal('0'))
            
            if transaction.merchant or transaction.description:
                merchant = transaction.merchant or transaction.description[:30]
                merchant_counts[merchant] = merchant_counts.get(merchant, 0) + 1
        
        summary.total_credits = credits
        summary.total_debits = debits
        summary.net_balance = credits - debits
        
        # Date range
        if dates:
            summary.date_range = (min(dates), max(dates))
        
        # Top categories by spending
        summary.top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Top merchants by transaction count
        summary.top_merchants = sorted(merchant_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return summary
    
    async def create_transaction_entities(self, transactions: List[ParsedTransaction], source_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Create Transaction entities from parsed transactions"""
        
        entities = []
        
        for i, transaction in enumerate(transactions):
            transaction_id = f"transaction_{hash(str(transaction))}_{i}"
            
            transaction_entity = {
                'id': transaction_id,
                'date': transaction.date if transaction.date else datetime.now(),
                'amount': float(transaction.amount) if transaction.amount else 0.0,
                'currency': transaction.currency,
                'description': transaction.description or "Unknown transaction",
                'category': transaction.category or 'other',
                'merchant': transaction.merchant or '',
                'account': transaction.account or '',
                'transaction_type': transaction.transaction_type or 'unknown',
                'source_document': source_path or '',
                'confidence_score': transaction.confidence,
                'created': datetime.now(),
                'updated': datetime.now()
            }
            
            entities.append(transaction_entity)
        
        return entities
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """Get enricher statistics"""
        return {
            'supported_formats': ['CSV', 'Bank Statement', 'Simple Text'],
            'categories': list(self.category_patterns.keys()),
            'patterns_count': len(self.patterns),
            'last_analysis': datetime.now().isoformat()
        }


# Global enricher instance
_finance_enricher: Optional[FinanceEnricher] = None


def get_finance_enricher() -> FinanceEnricher:
    """Get or create finance enricher instance"""
    global _finance_enricher
    if _finance_enricher is None:
        _finance_enricher = FinanceEnricher()
    return _finance_enricher


async def parse_statement(text: str, source_path: Optional[str] = None) -> Tuple[List[ParsedTransaction], FinancialSummary]:
    """Convenience function to parse a financial statement"""
    enricher = get_finance_enricher()
    return await enricher.parse_statement(text, source_path)