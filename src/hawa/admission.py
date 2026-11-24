"""Early admission checks, budget formatting, and output-path validation."""
import os
from pathlib import Path


def validate_new_output_file(path):
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError('Choose an output file path in a writable folder before starting')
    target = Path(path).expanduser()
    if target.exists():
        raise ValueError('Output file already exists ({}); choose a new file path or remove the existing file'.format(target))
    parent = target.resolve().parent
    if not parent.exists() or not parent.is_dir():
        raise ValueError('Output folder does not exist ({}); create it or choose an existing writable folder'.format(parent))
    if not os.access(str(parent), os.W_OK | os.X_OK):
        raise ValueError('Output folder is not writable ({}); choose a writable folder for the output file'.format(parent))
    return target


def validate_new_output_dir(directory):
    if not isinstance(directory, (str, Path)) or not str(directory).strip():
        raise ValueError('Choose an output folder path in a writable location before starting')
    target = Path(directory).expanduser().resolve()
    if target.exists():
        raise ValueError('Output folder already exists ({}); choose a new folder name'.format(target))
    ancestor = target.parent
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    if not ancestor.is_dir() or not os.access(str(ancestor), os.W_OK | os.X_OK):
        raise ValueError('Output folder parent is not writable ({}); choose a writable folder before starting'.format(ancestor))
    return target


def check_example_budget(estimated_mb, spec):
    limit_mb = float(spec.get('memory_limit_mb', 1024))
    if estimated_mb > limit_mb:
        raise ValueError(
            'Example allocation {:.0f} MiB exceeds the {:.0f} MiB case memory budget; '
            'reduce size or raise memory_limit_mb'.format(estimated_mb, limit_mb))
    return limit_mb


def check_case_budget(estimated_bytes, spec, neutral):
    limit_mb = int(spec.get('memory_limit_mb', 1024))
    estimated_peak_mb = estimated_bytes / 1024 ** 2
    if estimated_bytes > limit_mb * 1024 ** 2:
        raise ValueError(
            'Estimated peak allocation {:.0f} MiB exceeds the {} MiB case budget; '
            'increase dx, shrink the domain, or raise memory_limit_mb'.format(estimated_peak_mb, limit_mb))
    series_reserve_mb = 512 if (neutral and spec['neutral_precursor'].get('mode') == 'external') else 64
    estimated_with_series_mb = estimated_peak_mb if spec.get('boundary_field') else estimated_peak_mb + series_reserve_mb
    return {
        'estimated_peak_mb': estimated_peak_mb,
        'estimated_peak_with_series_mb': estimated_with_series_mb,
        'series_reserve_mb': series_reserve_mb,
        'memory_limit_mb': limit_mb,
    }


def check_refinement_budget(coarse_mb, fine_mb, limit_mb):
    combined_mb = coarse_mb + fine_mb
    if combined_mb > limit_mb:
        raise ValueError(
            'Combined coarse/fine memory {:.0f} MiB exceeds the {:.0f} MiB budget; '
            'increase dx, shrink the refinement region, or raise memory_limit_mb'.format(combined_mb, limit_mb))


def check_capture_budget(spec, reserve_mb):
    from .plugin import check_case
    report = check_case(spec)
    limit_mb = report['memory_limit_mb']
    total_mb = report['estimated_peak_mb'] + (0.0 if spec.get('boundary_field') else reserve_mb)
    if total_mb > limit_mb:
        raise ValueError(
            'Estimated peak allocation {:.0f} MiB (including {} MiB boundary series reserve) '
            'exceeds the {:.0f} MiB case budget; increase dx, shrink the domain, or raise memory_limit_mb'.format(
                total_mb, reserve_mb, limit_mb))
    return report


def preflight_job(request):
    if request.get('kind') == 'record':
        validate_new_output_dir(request.get('directory'))
    elif request.get('kind') == 'query':
        inner = request.get('request', {})
        if inner.get('op') == 'boundary' and inner.get('action') == 'capture':
            validate_new_output_file(inner.get('path'))
            spec = inner.get('case')
            if isinstance(spec, dict):
                reserve = 512 if spec.get('neutral_precursor', {}).get('mode') == 'external' else 64
                check_capture_budget(spec, reserve)
