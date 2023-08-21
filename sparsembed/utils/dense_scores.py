import torch

__all__ = ["dense_scores"]


def _build_index(activations: torch.Tensor, embeddings: torch.Tensor) -> dict:
    """Build index to score documents using activated tokens and embeddings."""
    index = []
    for tokens_activation, tokens_embeddings in zip(activations, embeddings):
        index.append(
            {
                token.item(): embedding
                for token, embedding in zip(tokens_activation, tokens_embeddings)
            }
        )
    return index


def _intersection(t1: torch.Tensor, t2: torch.Tensor) -> list:
    """Retrieve intersection between two tensors."""
    t1, t2 = t1.flatten(), t2.flatten()
    combined = torch.cat((t1, t2), dim=0)
    uniques, counts = combined.unique(return_counts=True, sorted=False)
    return uniques[counts > 1].tolist()


def _get_intersection(queries_activations: list, documents_activations: list) -> list:
    """Retrieve intersection of activated tokens between queries and documents."""
    return [
        _intersection(query_activations, document_activations)
        for query_activations, document_activations in zip(
            queries_activations,
            documents_activations,
        )
    ]


def _get_scores(
    anchor_embeddings_index: dict,
    positive_embeddings_index: dict,
    negative_embeddings_index: dict,
    positive_intersections: torch.Tensor,
    negative_intersections: torch.Tensor,
    func,
) -> dict[str, torch.Tensor]:
    """Computes similarity scores between queries and documents based on activated tokens embeddings"""
    positive_scores, negative_scores = [], []

    for (
        anchor_embedding_index,
        positive_embedding_index,
        negative_embedding_index,
        positive_intersection,
        negative_intersection,
    ) in zip(
        anchor_embeddings_index,
        positive_embeddings_index,
        negative_embeddings_index,
        positive_intersections,
        negative_intersections,
    ):
        if len(positive_intersections) > 0 and len(negative_intersections) > 0:
            positive_scores.append(
                func(
                    torch.stack(
                        [
                            anchor_embedding_index[token]
                            for token in positive_intersection
                        ],
                        dim=0,
                    )
                    * torch.stack(
                        [
                            positive_embedding_index[token]
                            for token in positive_intersection
                        ],
                        dim=0,
                    )
                )
            )

            negative_scores.append(
                func(
                    torch.stack(
                        [
                            anchor_embedding_index[token]
                            for token in negative_intersection
                        ],
                        dim=0,
                    )
                    * torch.stack(
                        [
                            negative_embedding_index[token]
                            for token in negative_intersection
                        ],
                        dim=0,
                    )
                )
            )

    return {
        "positive_scores": torch.stack(
            positive_scores,
            dim=0,
        ),
        "negative_scores": torch.stack(
            negative_scores,
            dim=0,
        ),
    }


def dense_scores(
    anchor_activations: torch.Tensor,
    positive_activations: torch.Tensor,
    negative_activations: torch.Tensor,
    anchor_embeddings: torch.Tensor,
    positive_embeddings: torch.Tensor,
    negative_embeddings: torch.Tensor,
    func=torch.sum,
) -> dict[str, torch.Tensor]:
    """Computes score between queries and documents intersected activated tokens.

    Parameters
    ----------
    queries_activations
        Queries activated tokens.
    queries_embeddings
        Queries activated tokens embeddings.
    documents_activations
        Documents activated tokens.
    documents_embeddings
        Documents activated tokens embeddings.
    func
        Either torch.sum or torch.mean. torch.mean is dedicated to training and
        torch.sum is dedicated to inference.

    Example
    ----------
    >>> from transformers import AutoModelForMaskedLM, AutoTokenizer
    >>> from sparsembed import model, utils
    >>> import torch

    >>> _ = torch.manual_seed(42)

    >>> model = model.SparsEmbed(
    ...     model=AutoModelForMaskedLM.from_pretrained("distilbert-base-uncased"),
    ...     tokenizer=AutoTokenizer.from_pretrained("distilbert-base-uncased"),
    ...     k_tokens=96,
    ... )

    >>> anchor_embeddings = model(
    ...     ["Paris", "Toulouse"],
    ... )

    >>> positive_embeddings = model(
    ...    ["Paris", "Toulouse"],
    ... )

    >>> negative_embeddings = model(
    ...    ["Toulouse", "Paris"],
    ... )

    >>> scores = utils.dense_scores(
    ...     anchor_activations=anchor_embeddings["activations"],
    ...     positive_activations=positive_embeddings["activations"],
    ...     negative_activations=negative_embeddings["activations"],
    ...     anchor_embeddings=anchor_embeddings["embeddings"],
    ...     positive_embeddings=positive_embeddings["embeddings"],
    ...     negative_embeddings=negative_embeddings["embeddings"],
    ...     func=torch.sum,
    ... )

    >>> scores
    {'positive_scores': tensor([216.5337, 214.3472], grad_fn=<StackBackward0>), 'negative_scores': tensor([103.8172, 103.8172], grad_fn=<StackBackward0>)}

    """
    anchor_embeddings_index = _build_index(
        activations=anchor_activations, embeddings=anchor_embeddings
    )

    positive_embeddings_index = _build_index(
        activations=positive_activations, embeddings=positive_embeddings
    )

    negative_embeddings_index = _build_index(
        activations=negative_activations, embeddings=negative_embeddings
    )

    positive_intersections = _get_intersection(
        queries_activations=anchor_activations,
        documents_activations=positive_activations,
    )

    negative_intersections = _get_intersection(
        queries_activations=anchor_activations,
        documents_activations=negative_activations,
    )

    return _get_scores(
        anchor_embeddings_index=anchor_embeddings_index,
        positive_embeddings_index=positive_embeddings_index,
        negative_embeddings_index=negative_embeddings_index,
        positive_intersections=positive_intersections,
        negative_intersections=negative_intersections,
        func=func,
    )