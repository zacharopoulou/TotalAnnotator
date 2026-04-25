"""Core package exports for TotalAnnotator."""

from bio_annotation.orchestrator import FetchOrchestrator
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

__all__ = ["Annotation", "Document", "FetchOrchestrator"]
