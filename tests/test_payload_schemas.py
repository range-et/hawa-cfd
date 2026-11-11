"""Repository rules for pydantic payload models in src/hawa (#68).

pydantic 2.13 is the last line for Rhino's Python 3.9. Its four known advisories
(GHSA-gj4f, GHSA-955g, GHSA-qpmf, GHSA-3r8g) stay unreachable only while every
model uses BaseModel, extra='forbid', Python-mode model_validate, and no Fraction
or URL types. The JSON Schema snapshots in docs/schemas are the documentation.
"""
import ast
import dataclasses
import fractions
import importlib
import json
import pkgutil
import typing
from pathlib import Path

import pydantic
import pytest
from pydantic import AnyUrl, BaseModel, ConfigDict, PostgresDsn
from typing_extensions import TypedDict, is_typeddict

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src' / 'hawa'
SNAPSHOTS = {'moving-body.schema.json': 'Body', 'motion-evaluation.schema.json': 'MotionEvaluation'}
# Names whose use would reach a known 2.13 advisory or leave Python-mode BaseModel validation.
FORBIDDEN_NAMES = {'Fraction', 'TypedDict', 'TypeAdapter', 'model_validate_json', 'validate_json',
                   'model_validate_strings', 'validate_strings', 'parse_raw', 'parse_file'}
FORBIDDEN_MODULES = {'fractions', 'pydantic.dataclasses', 'pydantic.networks'}


def hawa_models():
    import hawa
    for info in pkgutil.walk_packages(hawa.__path__, 'hawa.'):
        importlib.import_module(info.name)
    found, pending = set(), [BaseModel]
    while pending:
        for model in pending.pop().__subclasses__():
            pending.append(model)
            if model.__module__.startswith('hawa.'): found.add(model)
    return sorted(found, key=lambda model: model.__module__ + '.' + model.__qualname__)


def annotation_types(annotation):
    yield annotation
    for argument in typing.get_args(annotation):
        yield from annotation_types(argument)


def model_violations(model):
    """Rules 1, 2 and 4 on a live model: extra='forbid'; no dataclass, TypedDict, Fraction or URL field types."""
    problems = [] if model.model_config.get('extra') == 'forbid' else ["extra is not 'forbid'"]
    for name, field in model.model_fields.items():
        for kind in annotation_types(field.annotation):
            module = getattr(kind, '__module__', '')
            url = module == 'pydantic.networks' or (module.startswith('pydantic_core') and 'Url' in getattr(kind, '__name__', ''))
            structure = isinstance(kind, type) and (dataclasses.is_dataclass(kind) or is_typeddict(kind))
            if kind is fractions.Fraction or url or structure:
                problems.append(name + ' uses ' + getattr(kind, '__name__', str(kind)))
    return problems


def source_violations(text):
    """Rules 1, 3 and 4 in source: no pydantic dataclasses/TypedDict, JSON-mode validation, Fraction or URLs."""
    problems = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            module = getattr(node, 'module', None)
            modules = names if module is None else [module] + [module + '.' + n for n in names]
            problems += ['imports ' + m for m in modules if m in FORBIDDEN_MODULES]
        elif isinstance(node, ast.Attribute): names = [node.attr]
        elif isinstance(node, ast.Name): names = [node.id]
        else: continue
        problems += ['uses ' + n for n in names if n in FORBIDDEN_NAMES or n.endswith(('Url', 'Dsn'))]
    return problems


def test_every_hawa_model_follows_the_advisory_rules():
    # The advisory analysis covers exactly this release; re-check it before any change.
    assert (pydantic.VERSION, pydantic.__version__) == ('2.13.5', '2.13.5')
    models = hawa_models()
    assert {'Motion', 'Body', 'Sphere', 'Cylinder', 'Sdf', 'MotionEvaluation'} <= {m.__name__ for m in models}
    assert {m.__qualname__: model_violations(m) for m in models if model_violations(m)} == {}
    problems = {str(p.relative_to(ROOT)): source_violations(p.read_text()) for p in sorted(SOURCE.rglob('*.py'))}
    assert {path: found for path, found in problems.items() if found} == {}


def test_rule_checks_catch_each_violation():
    class Allows(BaseModel):
        model_config = ConfigDict(extra='allow')
    class Unset(BaseModel):
        value: float = 0.
    class Ratio(BaseModel):
        model_config = ConfigDict(extra='forbid')
        value: typing.Optional[fractions.Fraction] = None
    class Link(BaseModel):
        model_config = ConfigDict(extra='forbid')
        url: typing.List[AnyUrl] = []
        database: typing.Optional[PostgresDsn] = None
    @dataclasses.dataclass
    class Point:
        x: float
    class Pair(TypedDict):
        x: float
    class Nested(BaseModel):
        model_config = ConfigDict(extra='forbid')
        point: typing.Optional[Point] = None
        pair: typing.Dict[str, Pair] = {}
    assert model_violations(Allows) == model_violations(Unset) == ["extra is not 'forbid'"]
    assert model_violations(Ratio) == ['value uses Fraction']
    assert model_violations(Link) == ['url uses AnyUrl', 'database uses PostgresDsn']
    assert model_violations(Nested) == ['point uses Point', 'pair uses Pair']
    assert source_violations('from pydantic.dataclasses import dataclass\nfrom fractions import Fraction') == [
        'imports pydantic.dataclasses', 'imports fractions', 'uses Fraction']
    assert source_violations('from pydantic import TypeAdapter, HttpUrl\nModel.model_validate_json(text)') == [
        'uses TypeAdapter', 'uses HttpUrl', 'uses model_validate_json']
    assert source_violations('from typing_extensions import TypedDict\nModel.model_validate(data)') == ['uses TypedDict']
    assert source_violations('from pydantic import dataclasses, networks') == [
        'imports pydantic.dataclasses', 'imports pydantic.networks']
    assert source_violations('from pydantic import BaseModel\nimport fractions\nModel.model_validate(data)') == ['imports fractions']


@pytest.mark.parametrize('module,attribute,version', [('pydantic', 'VERSION', '2.14.3'),
                                                      ('pydantic_core', '__version__', '2.41.5')])
def test_import_refuses_a_different_pydantic_already_loaded(monkeypatch, module, attribute, version):
    """Rhino's script venvs share one interpreter; another plugin's pydantic must not be used."""
    import importlib.util
    from hawa import motion
    motion.require_pinned_pydantic()  # the pinned pair passes
    monkeypatch.setattr(importlib.import_module(module), attribute, version)
    found = ('2.14.3', '2.46.5') if module == 'pydantic' else ('2.13.5', '2.41.5')
    expected = ('pydantic {} with pydantic-core {} was already loaded, probably by another plugin or script. Hawa '
                'requires pydantic 2.13.5 with pydantic-core 2.46.5; restart Rhino before using moving bodies.').format(*found)
    with pytest.raises(RuntimeError) as error:
        motion.require_pinned_pydantic()
    assert str(error.value) == expected
    # A fresh import runs the guard before any pydantic name is used.
    spec = importlib.util.spec_from_file_location('hawa_motion_guard_probe', SOURCE / 'motion.py')
    with pytest.raises(RuntimeError) as error:
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
    assert str(error.value) == expected


@pytest.mark.parametrize('name', sorted(SNAPSHOTS))
def test_json_schema_snapshot_matches_live_model(name):
    from hawa import motion
    path = ROOT / 'docs' / 'schemas' / name
    live = getattr(motion, SNAPSHOTS[name]).model_json_schema()
    assert json.loads(path.read_text()) == live, 'Regenerate ' + name + ' as described in docs/payload-schemas.md'


def test_every_model_with_fields_is_documented_by_a_snapshot():
    documented = set()
    for name, model in SNAPSHOTS.items():
        schema = json.loads((ROOT / 'docs' / 'schemas' / name).read_text())
        documented |= {schema['title'], *schema.get('$defs', {})}
    assert {m.__name__ for m in hawa_models() if m.model_fields} <= documented
