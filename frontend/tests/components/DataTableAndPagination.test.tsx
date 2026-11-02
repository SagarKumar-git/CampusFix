import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { type Column, DataTable } from '../../src/components/ui/DataTable';
import { PaginationBar } from '../../src/components/ui/PaginationBar';

interface TestItem {
  id: string;
  name: string;
  category: string;
}

describe('DataTable and PaginationBar Components', () => {
  const columns: Column<TestItem>[] = [
    { id: 'name', header: 'Item Name', accessor: 'name' },
    { id: 'category', header: 'Category', accessor: 'category' },
  ];

  const testData: TestItem[] = [
    { id: '1', name: 'HDMI Cable', category: 'Audio-Visual' },
    { id: '2', name: 'Fluorescent Tube', category: 'Lighting' },
  ];

  describe('DataTable', () => {
    it('renders loading skeletons when isLoading is true', () => {
      render(
        <DataTable
          columns={columns}
          data={[]}
          keyField="id"
          isLoading={true}
        />
      );

      expect(screen.getAllByRole('status').length).toBeGreaterThan(0);
      expect(screen.queryByText('HDMI Cable')).not.toBeInTheDocument();
    });

    it('renders empty state when data array is empty', () => {
      render(
        <DataTable
          columns={columns}
          data={[]}
          keyField="id"
          emptyTitle="No Items Found"
          emptyDescription="Try adjusting your filter parameters."
        />
      );

      expect(screen.getByText('No Items Found')).toBeInTheDocument();
      expect(
        screen.getByText('Try adjusting your filter parameters.')
      ).toBeInTheDocument();
    });

    it('renders table headers and data rows correctly', () => {
      render(<DataTable columns={columns} data={testData} keyField="id" />);

      expect(
        screen.getByRole('columnheader', { name: /item name/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('columnheader', { name: /category/i })
      ).toBeInTheDocument();
      expect(screen.getAllByText('HDMI Cable').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Fluorescent Tube').length).toBeGreaterThanOrEqual(1);
    });

    it('handles row click callback when onRowClick is provided', async () => {
      const user = userEvent.setup();
      const handleRowClick = vi.fn();

      render(
        <DataTable
          columns={columns}
          data={testData}
          keyField="id"
          onRowClick={handleRowClick}
        />
      );

      const firstDesktopRow = screen.getAllByText('HDMI Cable')[0];
      await user.click(firstDesktopRow);
      expect(handleRowClick).toHaveBeenCalledWith(testData[0]);
    });
  });

  describe('PaginationBar', () => {
    it('renders item counts and page information', () => {
      render(
        <PaginationBar
          page={2}
          pageSize={10}
          total={35}
          totalPages={4}
          onPageChange={vi.fn()}
        />
      );

      expect(screen.getByText('Page 2 of 4')).toBeInTheDocument();
      expect(screen.getByText('11')).toBeInTheDocument(); // start item
      expect(screen.getByText('20')).toBeInTheDocument(); // end item
      expect(screen.getByText('35')).toBeInTheDocument(); // total
    });

    it('disables previous button on first page', () => {
      render(
        <PaginationBar
          page={1}
          pageSize={20}
          total={45}
          totalPages={3}
          onPageChange={vi.fn()}
        />
      );

      const prevBtn = screen.getByRole('button', { name: /previous page/i });
      const nextBtn = screen.getByRole('button', { name: /next page/i });

      expect(prevBtn).toBeDisabled();
      expect(nextBtn).toBeEnabled();
    });

    it('disables next button on last page', () => {
      render(
        <PaginationBar
          page={3}
          pageSize={20}
          total={45}
          totalPages={3}
          onPageChange={vi.fn()}
        />
      );

      const prevBtn = screen.getByRole('button', { name: /previous page/i });
      const nextBtn = screen.getByRole('button', { name: /next page/i });

      expect(prevBtn).toBeEnabled();
      expect(nextBtn).toBeDisabled();
    });

    it('calls onPageChange with decremented/incremented page', async () => {
      const user = userEvent.setup();
      const handlePageChange = vi.fn();

      render(
        <PaginationBar
          page={2}
          pageSize={10}
          total={50}
          totalPages={5}
          onPageChange={handlePageChange}
        />
      );

      const prevBtn = screen.getByRole('button', { name: /previous page/i });
      const nextBtn = screen.getByRole('button', { name: /next page/i });

      await user.click(nextBtn);
      expect(handlePageChange).toHaveBeenCalledWith(3);

      await user.click(prevBtn);
      expect(handlePageChange).toHaveBeenCalledWith(1);
    });
  });
});
