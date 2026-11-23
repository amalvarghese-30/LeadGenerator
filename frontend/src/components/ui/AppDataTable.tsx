import React from 'react';
import DataTable, { type DataTableProps } from 'datatables.net-react';
import DT from 'datatables.net-dt';
import 'datatables.net-responsive-dt';
import 'datatables.net-buttons-dt';
import { cn } from '../../utils/cn';

// Register core DataTables styling & responsive extension
DataTable.use(DT);

export interface AppDataTableProps<T = any> {
  columns: any[];
  data: T[];
  pageLength?: number;
  order?: any[];
  className?: string;
  searching?: boolean;
  responsive?: boolean;
  slots?: any;
  children?: React.ReactNode;
  options?: Record<string, any>;
}

export function AppDataTable<T = any>({
  columns,
  data,
  pageLength = 25,
  order = [[0, 'asc']],
  className,
  searching = true,
  responsive = true,
  slots,
  children,
  options = {},
}: AppDataTableProps<T>) {
  return (
    <div className="w-full overflow-x-auto rounded-xl border border-slate-200/80 bg-white shadow-sm">
      <DataTable
        data={data}
        columns={columns}
        slots={slots}
        className={cn('display responsive nowrap w-full text-left text-sm', className)}
        options={{
          pageLength,
          order,
          responsive,
          searching,
          lengthMenu: [
            [10, 25, 50, 100],
            [10, 25, 50, 100],
          ],
          language: {
            search: '',
            searchPlaceholder: 'Search records...',
            lengthMenu: 'Show _MENU_ entries',
            info: 'Showing _START_ to _END_ of _TOTAL_ entries',
            infoEmpty: 'Showing 0 to 0 of 0 entries',
            infoFiltered: '(filtered from _MAX_ total)',
            paginate: {
              first: '«',
              previous: '‹',
              next: '›',
              last: '»',
            },
          },
          dom: '<"p-4 flex flex-col sm:flex-row items-center justify-between gap-3 border-b border-slate-100"lf>rt<"p-4 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-slate-100"ip>',
          ...options,
        }}
      >
        {children}
      </DataTable>
    </div>
  );
}
