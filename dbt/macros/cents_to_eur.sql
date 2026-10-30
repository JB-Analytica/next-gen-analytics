{#- Sources store money as integer minor units (cents/pence/rappen) in the order's own currency.
    Marts expose euros because that is what a person reads; convert exactly once, here.

    `fx_rate` is units of the order currency per 1 EUR (ECB convention, as Frankfurter publishes
    it), so euros = minor / 100 / rate. It defaults to 1 for EUR amounts.

    Both arguments are parenthesised on purpose. Without that, `cents_to_eur('a - b')` expands
    to `a - b / 100` and divides only the last term. Pass an expression, get that expression
    converted. -#}
{% macro cents_to_eur(column, fx_rate='1') -%}
    round(({{ column }}) / 100.0 / ({{ fx_rate }}), 2)
{%- endmacro %}
