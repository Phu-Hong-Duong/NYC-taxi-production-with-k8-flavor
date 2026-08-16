{% test accepted_range(model, column_name, min_value=none, max_value=none, inclusive=true) %}
{#-
  accepted_range — our own generic test, written rather than installed.

  The obvious move is `dbt deps` + dbt_utils, which is one line of YAML and a
  package fetched from dbt Hub at build time. This program is $0 and offline by
  charter, pins every version it depends on, and needs exactly ONE macro out of
  that package. A twenty-line macro we own is cheaper to trust than a network
  dependency in the build path. Undo: add packages.yml and delete this file.

  Returns the OFFENDING ROWS — dbt's test contract is "a query that returns
  nothing when the data is good", and returning the rows is what makes a failure
  readable instead of just red.
-#}

with validation as (
    select {{ column_name }} as offending_value, *
    from {{ model }}
),

failures as (
    select * from validation
    where offending_value is null
    {%- if min_value is not none %}
       or offending_value {{ '<' if inclusive else '<=' }} {{ min_value }}
    {%- endif %}
    {%- if max_value is not none %}
       or offending_value {{ '>' if inclusive else '>=' }} {{ max_value }}
    {%- endif %}
)

select * from failures

{% endtest %}
