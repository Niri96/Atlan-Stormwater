st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Step 1: Enter Package")

package_input = st.data_editor(
    build_default_product_rows().drop(columns=["Discount %"], errors="ignore"),
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="package_input",
    column_config={
        "Pipe size mm": st.column_config.SelectboxColumn(
            "Pipe size mm",
            options=PIPE_SIZE_OPTIONS,
            required=True,
        ),
        "Quantity m": st.column_config.NumberColumn(
            "Quantity m",
            min_value=0.0,
            step=1.0,
        ),
        "RRP / m": st.column_config.NumberColumn(
            "RRP / m",
            min_value=0.0,
            step=5.0,
            format="$%.2f",
        ),
        "Cost / m": st.column_config.NumberColumn(
            "Cost / m",
            min_value=0.0,
            step=5.0,
            format="$%.2f",
        ),
        "Freight cost": st.column_config.NumberColumn(
            "Freight cost",
            min_value=0.0,
            step=50.0,
            format="$%.2f",
            help="Freight cost for this product line.",
        ),
    },
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# STEP 2: Interactive Discount
# =========================================================

package_input = package_input[package_input["Quantity m"] > 0].copy()

if not package_input.empty:

    discount_df = package_input.copy()

    if "Discount %" not in discount_df.columns:
        discount_df["Discount %"] = 0.0

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Step 2: Apply Discount")

    st.caption(
        "Adjust the discount by product line. The package contribution margin and margin at risk update automatically."
    )

    discount_input = st.data_editor(
        discount_df,
        use_container_width=True,
        hide_index=True,
        key="discount_input",
        column_config={
            "Pipe size mm": st.column_config.DisabledColumn("Pipe size mm"),
            "Quantity m": st.column_config.DisabledColumn("Quantity m"),
            "RRP / m": st.column_config.DisabledColumn("RRP / m"),
            "Cost / m": st.column_config.DisabledColumn("Cost / m"),
            "Freight cost": st.column_config.DisabledColumn("Freight cost"),
            "Discount %": st.column_config.NumberColumn(
                "Discount %",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                format="%.1f%%",
            ),
        },
    )

    product_lines = calculate_product_lines(discount_input)

    total_rrp_revenue = product_lines["RRP revenue"].sum()
    total_revenue = product_lines["Revenue"].sum()
    total_freight = product_lines["Freight cost"].sum()
    total_cost = product_lines["Total cost incl. freight"].sum()
    total_contribution = product_lines["Contribution $"].sum()

    rrp_contribution = product_lines["RRP contribution $"].sum()

    package_margin = safe_divide(total_contribution, total_revenue)
    rrp_margin = safe_divide(rrp_contribution, total_rrp_revenue)

    margin_lost_dollars = rrp_contribution - total_contribution
    margin_lost_pp = (rrp_margin - package_margin) * 100

    weighted_discount_pct = safe_divide(
        total_rrp_revenue - total_revenue,
        total_rrp_revenue,
    )

    st.markdown("</div>", unsafe_allow_html=True)


    # =========================================================
    # PACKAGE SUMMARY
    # =========================================================

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Package Summary")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("RRP revenue", f"${total_rrp_revenue:,.0f}")
    k2.metric("Discounted revenue", f"${total_revenue:,.0f}")
    k3.metric("Total freight", f"${total_freight:,.0f}")
    k4.metric("Contribution margin", f"{package_margin:.1%}")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Weighted discount", f"{weighted_discount_pct:.1%}")
    k6.metric("Contribution $", f"${total_contribution:,.0f}")
    k7.metric("Margin at risk", f"${margin_lost_dollars:,.0f}")
    k8.metric("Margin lost", f"{margin_lost_pp:.1f} pts")

    st.markdown("</div>", unsafe_allow_html=True)


    # =========================================================
    # MARGIN AT RISK MESSAGE
    # =========================================================

    if margin_lost_dollars > 0:
        st.warning(
            f"You are discounting the package by {weighted_discount_pct:.1%}. "
            f"This reduces contribution margin from {rrp_margin:.1%} to {package_margin:.1%}, "
            f"putting ${margin_lost_dollars:,.0f} of contribution margin at risk."
        )
    else:
        st.success(
            "No discount has been applied, so there is no contribution margin leakage versus RRP."
        )


    # =========================================================
    # PRODUCT LINE OUTPUT
    # =========================================================

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Product Line Margin Detail")

    output_cols = [
        "Pipe size mm",
        "Quantity m",
        "RRP / m",
        "Discount %",
        "Net sell price / m",
        "Cost / m",
        "Freight cost",
        "Revenue",
        "Contribution $",
        "Contribution margin %",
        "Margin lost $",
        "Margin lost percentage points",
    ]

    st.dataframe(
        product_lines[output_cols].style.format({
            "Quantity m": "{:,.2f}",
            "RRP / m": "${:,.2f}",
            "Discount %": "{:.1f}%",
            "Net sell price / m": "${:,.2f}",
            "Cost / m": "${:,.2f}",
            "Freight cost": "${:,.0f}",
            "Revenue": "${:,.0f}",
            "Contribution $": "${:,.0f}",
            "Contribution margin %": "{:.1%}",
            "Margin lost $": "${:,.0f}",
            "Margin lost percentage points": "{:.1f} pts",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

else:
    st.info("Enter at least one product line to calculate the package margin.")
