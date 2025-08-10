"""
Notes Enricher - Extract structure and meaning from documents
"""
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    """Structured content extracted from a document"""
    title: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = None
    todos: List[str] = None
    dates: List[str] = None
    contacts: List[str] = None
    urls: List[str] = None
    topics: List[str] = None
    sentiment: Optional[str] = None
    language: str = "en"
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.todos is None:
            self.todos = []
        if self.dates is None:
            self.dates = []
        if self.contacts is None:
            self.contacts = []
        if self.urls is None:
            self.urls = []
        if self.topics is None:
            self.topics = []


class NotesEnricher:
    """Analyzes and enriches document content"""
    
    def __init__(self):
        # Regex patterns for content extraction
        self.patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'(\+?1[-.\s]?)?(\()?[0-9]{3}(\))?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'),
            'url': re.compile(r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'),
            'date': re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}'),
            'todo': re.compile(r'(?:^|\n)\s*[-*•]\s*(?:TODO|To do|Action|Task)[:.]?\s*(.+?)(?=\n|$)', re.IGNORECASE | re.MULTILINE),
            'checkbox_todo': re.compile(r'(?:^|\n)\s*\[[ x]\]\s*(.+?)(?=\n|$)', re.MULTILINE),
            'heading': re.compile(r'^#+\s+(.+)$', re.MULTILINE),
            'bold_text': re.compile(r'\*\*(.+?)\*\*|__(.+?)__'),
        }
        
        # Common keywords to extract topics
        self.topic_keywords = {
            'technology': ['software', 'hardware', 'programming', 'code', 'development', 'tech', 'digital', 'AI', 'machine learning'],
            'business': ['revenue', 'profit', 'sales', 'marketing', 'strategy', 'business', 'company', 'corporate'],
            'health': ['exercise', 'diet', 'wellness', 'medical', 'health', 'fitness', 'nutrition'],
            'finance': ['money', 'budget', 'investment', 'financial', 'bank', 'payment', 'cost', 'expense'],
            'education': ['learning', 'study', 'research', 'academic', 'university', 'school', 'knowledge'],
            'personal': ['family', 'friends', 'personal', 'home', 'life', 'relationship']
        }
        
        logger.info("📝 Notes enricher initialized")
    
    async def enrich_content(self, text: str, source_path: Optional[str] = None) -> ExtractedContent:
        """Enrich document content with extracted information"""
        
        if not text or not text.strip():
            return ExtractedContent()
        
        # Extract basic elements
        title = self._extract_title(text, source_path)
        summary = self._generate_summary(text)
        keywords = self._extract_keywords(text)
        todos = self._extract_todos(text)
        dates = self._extract_dates(text)
        contacts = self._extract_contacts(text)
        urls = self._extract_urls(text)
        topics = self._identify_topics(text, keywords)
        sentiment = self._analyze_sentiment(text)
        language = self._detect_language(text)
        
        return ExtractedContent(
            title=title,
            summary=summary,
            keywords=keywords,
            todos=todos,
            dates=dates,
            contacts=contacts,
            urls=urls,
            topics=topics,
            sentiment=sentiment,
            language=language
        )
    
    def _extract_title(self, text: str, source_path: Optional[str] = None) -> Optional[str]:
        """Extract or generate a title for the document"""
        
        # Try to find explicit headings first
        heading_matches = self.patterns['heading'].findall(text)
        if heading_matches:
            # Use the first heading as title
            title = heading_matches[0].strip()
            if len(title) < 100:  # Reasonable title length
                return title
        
        # Try to find bold text that could be a title
        bold_matches = self.patterns['bold_text'].findall(text)
        for match in bold_matches:
            # match is a tuple from alternation groups
            bold_text = match[0] or match[1]
            if bold_text and len(bold_text.strip()) < 100:
                return bold_text.strip()
        
        # Fall back to using the first sentence as title
        sentences = text.strip().split('\n')
        for sentence in sentences:
            cleaned = sentence.strip()
            if cleaned and len(cleaned) > 10 and len(cleaned) < 100:
                # Remove common prefixes
                for prefix in ['Subject:', 'Title:', 'Re:', 'From:']:
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[len(prefix):].strip()
                
                if cleaned:
                    return cleaned
        
        # Generate title from filename if available
        if source_path:
            from pathlib import Path
            filename = Path(source_path).stem
            # Clean up filename
            title = re.sub(r'[_-]', ' ', filename)
            title = re.sub(r'\d{8}', '', title)  # Remove dates
            title = title.strip()
            if title:
                return title.title()
        
        return None
    
    def _generate_summary(self, text: str, max_length: int = 200) -> Optional[str]:
        """Generate a brief summary of the content"""
        
        if len(text) <= max_length:
            return text.strip()
        
        # Simple extractive summarization - take first few sentences
        sentences = re.split(r'[.!?]+', text)
        summary_sentences = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if current_length + len(sentence) > max_length - 10:  # Leave room for ellipsis
                break
                
            summary_sentences.append(sentence)
            current_length += len(sentence)
        
        if summary_sentences:
            summary = '. '.join(summary_sentences)
            if current_length < len(text):
                summary += "..."
            return summary
        
        # If no good sentences, just truncate
        return text[:max_length-3] + "..."
    
    def _extract_keywords(self, text: str, max_keywords: int = 20) -> List[str]:
        """Extract important keywords from the text"""
        
        # Simple keyword extraction based on word frequency and importance
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
            'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
        
        # Extract words and count frequency
        words = re.findall(r'\b[A-Za-z]{3,}\b', text.lower())
        word_freq = {}
        
        for word in words:
            if word not in stop_words and len(word) >= 3:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sort by frequency and return top keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, freq in sorted_words[:max_keywords] if freq > 1]
        
        return keywords
    
    def _extract_todos(self, text: str) -> List[str]:
        """Extract TODO items and action items"""
        
        todos = []
        
        # Find explicit TODO markers
        todo_matches = self.patterns['todo'].findall(text)
        todos.extend([todo.strip() for todo in todo_matches if todo.strip()])
        
        # Find checkbox-style todos
        checkbox_matches = self.patterns['checkbox_todo'].findall(text)
        todos.extend([todo.strip() for todo in checkbox_matches if todo.strip()])
        
        # Look for action-oriented phrases
        action_patterns = [
            r'need to (.+?)(?=\.|;|\n|$)',
            r'should (.+?)(?=\.|;|\n|$)',
            r'must (.+?)(?=\.|;|\n|$)',
            r'remember to (.+?)(?=\.|;|\n|$)',
            r'action item[:.]?\s*(.+?)(?=\.|;|\n|$)'
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            todos.extend([match.strip() for match in matches if match.strip()])
        
        # Clean and deduplicate todos
        cleaned_todos = []
        seen = set()
        
        for todo in todos:
            if len(todo) > 5 and len(todo) < 200:  # Reasonable length
                todo_lower = todo.lower()
                if todo_lower not in seen:
                    seen.add(todo_lower)
                    cleaned_todos.append(todo)
        
        return cleaned_todos[:10]  # Limit to 10 todos
    
    def _extract_dates(self, text: str) -> List[str]:
        """Extract date mentions from text"""
        
        dates = []
        date_matches = self.patterns['date'].findall(text)
        
        for date_str in date_matches:
            try:
                # Try to parse and normalize the date
                # This is simplified - could use dateutil.parser for more robust parsing
                dates.append(date_str.strip())
            except:
                continue
        
        return list(set(dates))  # Remove duplicates
    
    def _extract_contacts(self, text: str) -> List[str]:
        """Extract contact information (emails, phone numbers)"""
        
        contacts = []
        
        # Extract emails
        email_matches = self.patterns['email'].findall(text)
        contacts.extend(email_matches)
        
        # Extract phone numbers
        phone_matches = self.patterns['phone'].findall(text)
        # phone pattern returns tuples, flatten them
        for match in phone_matches:
            if isinstance(match, tuple):
                phone = ''.join(str(part) for part in match if part)
            else:
                phone = match
            contacts.append(phone)
        
        return list(set(contacts))  # Remove duplicates
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text"""
        
        url_matches = self.patterns['url'].findall(text)
        return list(set(url_matches))  # Remove duplicates
    
    def _identify_topics(self, text: str, keywords: List[str]) -> List[str]:
        """Identify topics based on keywords and content"""
        
        text_lower = text.lower()
        topics = []
        
        # Check each topic category
        for topic, topic_words in self.topic_keywords.items():
            score = 0
            
            # Check for topic words in text
            for word in topic_words:
                if word.lower() in text_lower:
                    score += text_lower.count(word.lower())
            
            # Check for topic words in extracted keywords
            for keyword in keywords:
                if keyword.lower() in topic_words:
                    score += 2  # Higher weight for keywords
            
            # If we found evidence for this topic, include it
            if score > 0:
                topics.append(topic)
        
        return topics
    
    def _analyze_sentiment(self, text: str) -> Optional[str]:
        """Basic sentiment analysis"""
        
        # Simple rule-based sentiment analysis
        positive_words = {
            'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 
            'love', 'like', 'enjoy', 'happy', 'pleased', 'satisfied', 'success',
            'successful', 'achievement', 'accomplished', 'progress', 'improvement'
        }
        
        negative_words = {
            'bad', 'terrible', 'awful', 'horrible', 'hate', 'dislike', 'angry',
            'frustrated', 'disappointed', 'failed', 'failure', 'problem', 'issue',
            'error', 'mistake', 'wrong', 'difficult', 'hard', 'struggle'
        }
        
        words = re.findall(r'\b[A-Za-z]+\b', text.lower())
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        if positive_count > negative_count and positive_count > 2:
            return "positive"
        elif negative_count > positive_count and negative_count > 2:
            return "negative"
        else:
            return "neutral"
    
    def _detect_language(self, text: str) -> str:
        """Basic language detection (simplified)"""
        
        # Very basic language detection - could use langdetect library for better results
        # For now, just assume English
        return "en"
    
    async def create_note_entity(self, content: ExtractedContent, original_text: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Create a NoteSummary entity from enriched content"""
        
        entity_id = f"note_{hash(original_text)}_{int(datetime.now().timestamp())}"
        
        # Build source paths
        source_paths = []
        if file_path:
            source_paths.append(file_path)
        
        # Combine topics and keywords for tags
        tags = list(set(content.topics + content.keywords[:5]))  # Limit keywords for tags
        
        note_entity = {
            'id': entity_id,
            'title': content.title or "Untitled Document",
            'snippet': content.summary or original_text[:200] + "..." if len(original_text) > 200 else original_text,
            'tags': tags,
            'backlinks_count': 0,
            'source_paths': source_paths,
            'word_count': len(original_text.split()),
            'key_topics': content.topics,
            'sentiment': content.sentiment,
            'language': content.language,
            'created': datetime.now(),
            'updated': datetime.now()
        }
        
        return note_entity
    
    async def extract_related_entities(self, content: ExtractedContent) -> List[Dict[str, Any]]:
        """Extract related entities (tasks, contacts) from enriched content"""
        
        entities = []
        
        # Create task entities from todos
        for i, todo in enumerate(content.todos):
            task_id = f"task_extracted_{hash(todo)}_{i}"
            task_entity = {
                'id': task_id,
                'title': todo,
                'due': None,
                'status': 'todo',
                'plugin_source': 'notes_enricher',
                'description': f"Extracted from document analysis",
                'priority': 'medium',
                'tags': ['extracted', 'document'],
                'created': datetime.now(),
                'updated': datetime.now()
            }
            entities.append(('task', task_entity))
        
        # Create contact entities from extracted contact info
        for contact_info in content.contacts:
            if '@' in contact_info:  # Email
                contact_id = f"contact_email_{hash(contact_info)}"
                contact_entity = {
                    'id': contact_id,
                    'display_name': contact_info.split('@')[0].replace('.', ' ').title(),
                    'emails': [contact_info],
                    'phones': [],
                    'relations': [],
                    'tags': ['extracted', 'document'],
                    'notes': 'Extracted from document analysis',
                    'created': datetime.now(),
                    'updated': datetime.now()
                }
                entities.append(('contact', contact_entity))
        
        return entities


# Global enricher instance
_notes_enricher: Optional[NotesEnricher] = None


def get_notes_enricher() -> NotesEnricher:
    """Get or create notes enricher instance"""
    global _notes_enricher
    if _notes_enricher is None:
        _notes_enricher = NotesEnricher()
    return _notes_enricher


async def enrich_document(text: str, source_path: Optional[str] = None) -> ExtractedContent:
    """Convenience function to enrich a document"""
    enricher = get_notes_enricher()
    return await enricher.enrich_content(text, source_path)