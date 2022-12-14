#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#


from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, ValidationError


class Model(BaseModel):
    class Config:
        extra = "forbid"

    name: str
    dimensions: list[str]
    metrics: list[str]
    filter: Optional[str]


class Explainer:
    """
    ERRORS_MAPPING holds an external `Pydantic.ValidationError` types and their placeholders.
    {
        key: str = <Pydantic.ValidationError Type>,
        value: tuple(str, list) = (<explainable message>, <list as placeholder>
    }

    """

    errors_mapping = {
        "value_error.missing": ("fields required", []),
        "value_error.extra": ("fields not permitted", []),
        "type_error": ("type errors", []),
    }

    def parse(self, errors: List[Dict]) -> str:
        for error in errors:
            field_name, error_type = error.get("loc")[0], error.get("type")

            # general errors
            if error_type in self.errors_mapping:
                self.errors_mapping.get(error_type)[1].append(field_name)

            # type errors
            if "type_error" in error_type:
                error_type, _type = error_type.split(".")
                self.errors_mapping.get(error_type)[1].append((field_name, f"{_type} is required"))

    def explain(self, errors: List[Dict]):
        """
        General Errors are explained first.
        Such as:
            - missing required field
            - presence of non-permitted fields

        Type Errors are explained last.
        If model attribute has invalid type provided, like list, but str was required and etc:
            - str is required,
            - ...
        """

        self.parse(errors)

        for error_type in self.errors_mapping:
            msg, errors = self.errors_mapping.get(error_type)
            if errors:
                return f"{msg} {errors}"


@dataclass
class CustomReportsValidator:

    custom_reports: Union[List[Dict], Dict] = Field(default_factory=list)

    def __post_init__(self):
        self.reports: list = [self.custom_reports] if not isinstance(self.custom_reports, list) else self.custom_reports
        self.model: Model = Model
        self.explainer: Explainer = Explainer()

    def validate(self):

        # local import of airbyte_cdk dependencies
        from airbyte_cdk.models import FailureType
        from airbyte_cdk.utils.traced_exception import AirbyteTracedException

        try:
            for report in self.reports:
                self.model.parse_obj(report)
        except ValidationError as e:
            raise AirbyteTracedException(
                message=None,
                internal_message=f"Custom Reports has invalid structure in report: {report}, errors: {self.explainer.explain(e.errors())}",
                failure_type=FailureType.config_error,
            ) from None
