from pydantic import BaseModel

class AliasModel(BaseModel):

    def model_dump_json(self, *args, **kwargs) -> str:
        kwargs.setdefault('by_alias', True)
        kwargs.setdefault('indent', 2)
        return super().model_dump_json(*args, **kwargs)