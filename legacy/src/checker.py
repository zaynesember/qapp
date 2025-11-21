import importlib

available_imports = [
    'precinct',
    'office',
    'party_detailed',
    'party_simplified',
    'mode',
    'votes',
    'county_name',
    'county_fips',
    'jurisdiction_name',
    'jurisdiction_fips',
    'candidate',
    'district',
    'magnitude',
    'dataverse',
    'year',
    'stage',
    'state',
    'special',
    'writein',
    'state_po',
    'state_fips',
    'state_cen',
    'state_ic',
    'date',
    # 'readme_check',
    ]

def get_fields_to_modules():
    found_fields = dict()
    #field_module = importlib.import_module('.', package='fields')
    for available_import in available_imports:
        try:
            module = importlib.import_module(f'electioncleaner.src.fields.{available_import}')
        except ModuleNotFoundError:
            module = importlib.import_module(f'src.fields.{available_import}')
        module_class = getattr(module, available_import.capitalize())
        found_fields[available_import] = module_class
    return found_fields

if __name__ in ['__main__', 'electioncleaner.src.checker']:
    fields = get_fields_to_modules()
    for (field, module_class) in fields.items():
        globals()[field] = module_class()

    __all__ = tuple(available_imports) + ('get_fields_to_modules',)
else:
    __all__ = ('get_fields_to_modules',)