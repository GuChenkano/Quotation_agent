
import logging
from typing import List, Dict, Any
from ragas import evaluate
from ragas.metrics import (
    Faithfulness,
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    AnswerCorrectness
)
from datasets import Dataset

logger = logging.getLogger(__name__)

class RagasEvaluator:
    """
    Ragas 评估器封装类
    """
    def __init__(self, llm, embeddings):
        self.llm = llm
        self.embeddings = embeddings
        # 配置 ragas 使用的 metrics
        self.metrics = [
            Faithfulness(),
            AnswerRelevancy(),
            # ContextPrecision(), 
            # AnswerCorrectness() 
        ]
        
    def evaluate_single(self, question: str, answer: str, contexts: List[str], ground_truth: str = None) -> Dict[str, float]:
        """
        对单次问答进行评估
        """
        data_dict = {
            "question": [question],
            "answer": [answer],
            "contexts": [contexts],
        }
        
        if ground_truth:
            data_dict["ground_truth"] = [ground_truth]
            metrics_to_use = self.metrics + [ContextPrecision(), AnswerCorrectness()]
        else:
            data_dict["ground_truth"] = [""] 
            metrics_to_use = self.metrics

        dataset = Dataset.from_dict(data_dict)
        
        try:
            for m in metrics_to_use:
                if hasattr(m, 'llm'):
                    m.llm = self.llm
                if hasattr(m, 'embeddings'):
                    m.embeddings = self.embeddings
            
            results = evaluate(
                dataset=dataset,
                metrics=metrics_to_use,
                llm=self.llm,
                embeddings=self.embeddings,
                raise_exceptions=False
            )
            
            if hasattr(results, 'to_pandas'):
                df = results.to_pandas()
                if not df.empty:
                    result_dict = df.iloc[0].to_dict()
                    clean_dict = {}
                    for k, v in result_dict.items():
                        if k in ["question", "answer", "contexts", "ground_truth"]:
                            continue
                        try:
                            clean_dict[k] = float(v)
                        except (ValueError, TypeError):
                            pass
                    return clean_dict
            
            if hasattr(results, 'scores'):
                return results.scores
                
            return dict(results)
        except Exception as e:
            logger.error(f"Ragas 评估失败: {e}")
            return {}
