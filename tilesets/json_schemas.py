tiles_post_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "definitions": {
        "multivecRowAggregationOptions": {
            "type": "object",
            "required": ["aggGroups", "aggFunc"],
            "additionalProperties": False,
            "properties": {
                "aggGroups": {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            { "type": "integer" },
                            { "type": "array", "items": { "type": "integer" }}
                        ]
                    }
                },
                "aggFunc": {
                    "type": "string",
                    "enum": ["sum", "mean", "median", "std", "var", "min", "max"]
                }
            }
        }
    },
    "type": "array",
    "items": {
        "type": "object",
        "required": ["tilesetUid", "tileIds"],
        "properties": {
            "tilesetUid": { "type": "string" },
            "tileIds": { "type": "array", "items": { "type": "string" }},
            "options": {
                "oneOf": [
                    { "$ref": "#/definitions/multivecRowAggregationOptions" }
                ]
            }
        }
    }
}