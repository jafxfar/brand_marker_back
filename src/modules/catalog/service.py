from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Category
from src.modules.catalog.schemas import CategoryTree


class CategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tree(self) -> list[CategoryTree]:
        result = await self.db.execute(select(Category).order_by(Category.id))
        categories = list(result.scalars().all())
        by_parent: dict[int | None, list[Category]] = {}
        for cat in categories:
            by_parent.setdefault(cat.parent_id, []).append(cat)

        def build(parent_id: int | None) -> list[CategoryTree]:
            nodes = []
            for cat in by_parent.get(parent_id, []):
                nodes.append(
                    CategoryTree(
                        id=cat.id,
                        parent_id=cat.parent_id,
                        name=cat.name,
                        slug=cat.slug,
                        children=build(cat.id),
                    )
                )
            return nodes

        return build(None)
