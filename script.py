if target_record.empty:
            st.warning(f"Data for {date_str} is missing. Here are the historical rankings for {short_date_str}:")
            st.dataframe(df_day_sorted.head(10).assign(Date=lambda x: x["Date"].dt.date))
        else:
            # 基础排名（历史同日期的排名）
            rank = target_record.iloc[0]["Rank"]
            temp = target_record.iloc[0]["MaxTemp"]
            total_years = len(df_day_sorted)

            st.success(f"### On {date_str}, the maximum temperature in {city_name} was {temp:.1f}{temp_unit}")
            st.write(f"🎉 This day ranks as the **#{rank} hottest** {short_date_str} since 1950 (out of {total_years} years of data).")

            # --- 新增的三个维度统计 ---
            target_month_name = selected_date.strftime('%B')
            
            # 1. 当月排名 (Month & Year)
            df_month = df[(df["Date"].dt.year == target_year) & (df["Date"].dt.month == target_month)].copy()
            df_month["Rank"] = df_month["MaxTemp"].rank(method="min", ascending=False).astype(int)
            month_rank = df_month[df_month["Date"].dt.date == selected_date]["Rank"].iloc[0]
            total_days_month = len(df_month)
            
            # 2. 当年排名 (Year)
            df_year = df[df["Date"].dt.year == target_year].copy()
            df_year["Rank"] = df_year["MaxTemp"].rank(method="min", ascending=False).astype(int)
            year_rank = df_year[df_year["Date"].dt.date == selected_date]["Rank"].iloc[0]
            total_days_year = len(df_year)
            
            # 3. 历史总排名 (All-time ever)
            df_all = df.copy()
            df_all["Rank"] = df_all["MaxTemp"].rank(method="min", ascending=False).astype(int)
            all_time_rank = df_all[df_all["Date"].dt.date == selected_date]["Rank"].iloc[0]
            total_days_ever = len(df_all)
            top_percent = (all_time_rank / total_days_ever) * 100
            
            # 优化极小百分比的显示
            percent_str = "< 0.01%" if top_percent < 0.01 else f"{top_percent:.2f}%"

            # 易懂且通顺的润色文案
            st.markdown(f"""
            **More Heat Stats for this date:**
            - 📅 **#{month_rank} hottest day** in {target_month_name} {target_year}.
            - 📆 **#{year_rank} hottest day** of the entire year in {target_year}.
            - 🌎 **Top {percent_str} hottest day of all time** in {city_name} (Ranked #{all_time_rank:,} out of {total_days_ever:,} total recorded days).
            """)

            st.markdown("---")
            st.subheader(f"🔥 Top 10 Hottest {short_date_str} on Record for {city_name}")

            display_df = df_day_sorted.head(10).copy()
            display_df["Date"] = display_df["Date"].dt.date
            display_df = display_df.rename(columns={
                "Date": "Date", 
                "MaxTemp": f"Max Temp ({temp_unit})", 
                "Rank": "Historical Rank"
            })

            display_df[f"Max Temp ({temp_unit})"] = display_df[f"Max Temp ({temp_unit})"].map(lambda x: f"{x:.1f}")

            st.dataframe(display_df, hide_index=True, use_container_width=True)
