#!/usr/bin/env python3

import os
import asyncio
from llama_index.core import Settings
from llama_index.core.schema import BaseNode, TextNode, MetadataMode, TransformComponent
from llama_index.core.llms import LLM
from llama_index.core.prompts.base import PromptTemplate
from llama_index.core.prompts.default_prompts import DEFAULT_SUMMARY_PROMPT
from llama_index.core.indices.prompt_helper import PromptHelper
from typing import Optional, Any

import pickle
from settings import parse_args_and_setup


class Tree:
    """A tree of nodes that replicates the original directory stucture."""

    def __init__(self) -> None:
        self._children = {}
        self._nodes = []

    def add(self, path: list[str], node: BaseNode) -> None:
        """Add a node to the tree."""
        if path:
            if path[0] not in self._children:
                self._children[path[0]] = Tree()
            self._children[path[0]].add(path[1:], node)
        else:
            self._nodes.append(node)

    def compact(self) -> None:
        """Merge nodes with only a single child with that child."""
        children_new = {}
        for prefix, c in self._children.items():
            c.compact()
            if len(c._children) == 1:
                k = next(iter(c._children))
                children_new[prefix + os.sep + k] = c._children[k]
            else:
                children_new[prefix] = c
        self._children = children_new

    async def _asummarize(
        self,
        llm: LLM,
        prompt: PromptTemplate,
        prompt_helper: PromptHelper,
        nodes: list[BaseNode],
    ) -> str:
        """Summarize a list of nodes by iteratively fitting the maximum into the context window."""
        texts = [node.get_content(metadata_mode=MetadataMode.LLM) for node in nodes]

        while True:
            chunks = prompt_helper.repack(prompt, texts)
            tasks = [llm.apredict(prompt, context_str=chunk) for chunk in chunks]
            summaries = await asyncio.gather(*tasks)
            if len(summaries) == 1:
                return summaries[0]
            texts = summaries

    async def abuild(
        self,
        llm: LLM,
        prompt: PromptTemplate,
        prompt_helper: PromptHelper,
        path: Optional[str] = None,
    ) -> None:
        """Generate a summary of children for each tree node recursively."""
        if self._children:
            if path is None:
                prefix = ""
            else:
                prefix = path + os.sep
            await asyncio.gather(
                *[
                    c.abuild(llm, prompt, prompt_helper, prefix + k)
                    for k, c in self._children.items()
                ]
            )

            self._summary = TextNode(
                text=await self._asummarize(
                    llm,
                    prompt,
                    prompt_helper,
                    [c._summary for c in self._children.values()],
                ),
                metadata={
                    "file_path": "[root_directory]" if path is None else path,
                    "subpaths": ":".join(self._children.keys()),
                },
            )
        else:
            self._summary = TextNode(
                text=await self._asummarize(llm, prompt, prompt_helper, self._nodes),
                metadata={"file_path": path},
            )

    def gather(self) -> list[BaseNode]:
        """Collect all the summaries stored in the nodes."""
        s = []
        for c in self._children.values():
            s += c.gather()
        s.append(self._summary)
        return s

    def print(self, depth: int = 0) -> None:
        """Print out the tree structure."""
        for k, c in self._children.items():
            print("\t" * depth + k)
            c.print(depth + 1)


class RecursiveDirectorySummarize(TransformComponent):
    """
    Generate summary nodes by recursively summarizing nodes loaded from a directory.

    The nodes must contain `file_path` in their metadata to indicate the path of
    the document it originates from. The nodes in the same document are summarized
    first into a new node. Then, the nodes in the same directories are summarized
    together to produce parent nodes. This process will repeat recursively until
    the root directory is reached.

    Args:
        verbose (bool, optional): If `True`, print verbose output including the built tree. Defaults to `False`.
        summaries_only (bool, optional): If `True`, return only the summary nodes, else include the original (leaf) nodes. Defaults to `False`.
        llm (LLM, optional): LLM instance to use for building summaries. Defaults to `Settings.LLM`.
        prompt (PormptTemplate, optional): Prompt template for generating summaries. Defaults to `DEFAULT_SUMMARY_PROMPT`.
    """

    verbose: bool = False
    summaries_only: bool = False
    llm: Optional[LLM] = None
    prompt: PromptTemplate = DEFAULT_SUMMARY_PROMPT
    prompt_helper: Optional[PromptHelper]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.llm = self.llm or Settings.llm
        self.prompt_helper = PromptHelper.from_llm_metadata(self.llm.metadata)

    async def acall(self, nodes: list[BaseNode], **kwargs: Any) -> list[BaseNode]:
        t = Tree()
        for node in nodes:
            path = node.metadata["file_path"]
            path = os.path.normpath(path).split(os.sep)
            t.add(path, node)
        t.compact()

        if self.verbose:
            print("Built tree:")
            t.print()

        await t.abuild(self.llm, self.prompt, self.prompt_helper)
        summary_nodes = t.gather()
        if self.summaries_only:
            return summary_nodes
        else:
            return nodes + summary_nodes

    def __call__(self, nodes: list[BaseNode], **kwargs: Any) -> list[BaseNode]:
        return asyncio.run(self.acall(nodes, **kwargs))


# NOTE: Currently for testing only, may need a more elegant implementation in the future
def main() -> None:
    parse_args_and_setup()
    with open("nodes.pkl", "rb") as file:
        nodes = pickle.load(file)

    rds = RecursiveDirectorySummarize(verbose=True, summaries_only=True)
    summary_nodes = rds(nodes)
    with open("summary_nodes.txt", "w") as file:
        for node in summary_nodes:
            file.write(node.get_content(metadata_mode=MetadataMode.LLM))
            file.write("\n----------------\n\n")


if __name__ == "__main__":
    main()
