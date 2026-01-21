{% macro read_delta(table_name) %}
    delta_scan('{{ var("bronze_path") }}/{{ table_name }}')
{% endmacro %}
