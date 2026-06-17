/**
 * BillOfMaterials — Recommended HPE Aruba equipment list
 * 
 * Clean table with product names, quantities, and plain-English purpose.
 * Export button stubs for PDF/CSV.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';

// Default pricing — replace with Global Pricing Service API call for production.
const PRICING_DATA = {
  'Aruba CX 6300M Switch':   { USD: 4500, EUR: 4150, INR: 375000 },
  'Aruba CX 6200F 24G Switch': { USD: 1200, EUR: 1100, INR: 99000 },
  'Aruba AP-635 Access Point': { USD: 850,  EUR: 780,  INR: 70500 },
  'Aruba 9004 Gateway':        { USD: 1500, EUR: 1380, INR: 124500 },
  'Cat6A Cabling Kit':         { USD: 200,  EUR: 185,  INR: 16500 },
};

const CURRENCIES = [
  { code: 'USD', symbol: '$', label: 'North America (USD)' },
  { code: 'EUR', symbol: '€', label: 'Europe (EUR)' },
  { code: 'INR', symbol: '₹', label: 'India (INR)' },
];

export default function BillOfMaterials() {
  const navigate = useNavigate();
  const { state } = useProject();
  const [currencyCode, setCurrencyCode] = useState('USD');
  
  const bom = state.proposedDesign?.bom || [];
  const activeCurrency = CURRENCIES.find(c => c.code === currencyCode);

  // Calculate prices based on selection
  const getPrice = (product) => PRICING_DATA[product]?.[currencyCode] || 0;
  const grandTotal = bom.reduce((acc, item) => acc + (getPrice(item.product) * item.qty), 0);

  if (!bom.length) {
    return (
      <div className="p-8 text-center mt-20">
        <span className="material-symbols-outlined text-6xl text-outline mb-4">receipt_long</span>
        <h2 className="text-xl font-bold text-on-surface mb-2">No bill of materials yet</h2>
        <p className="text-on-surface-variant mb-6">Generate a design first to see recommended equipment.</p>
        <button onClick={() => navigate('/requirements')} className="px-6 py-3 bg-primary text-on-primary font-bold rounded-lg">Go to Requirements</button>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-8 custom-scrollbar">
      <div className="max-w-6xl mx-auto">
      <header className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
        <div>
          <div className="flex items-center gap-2 text-primary mb-2">
            <span className="material-symbols-outlined text-sm">receipt_long</span>
            <span className="text-xs font-[family-name:var(--font-mono)] uppercase tracking-[0.2em]">Equipment List</span>
          </div>
          <h1 className="text-3xl font-bold font-[family-name:var(--font-headline)] text-on-surface tracking-tight">Bill of Materials</h1>
          <p className="text-on-surface-variant mt-2">Recommended HPE Aruba equipment for your network.</p>
        </div>
        
        <div className="flex flex-wrap gap-3">
          {/* Region/Currency Selector */}
          <div className="relative group">
            <select 
              value={currencyCode}
              onChange={(e) => setCurrencyCode(e.target.value)}
              className="appearance-none px-4 py-2 bg-surface-container border border-outline-variant/30 text-on-surface text-sm font-medium rounded-lg hover:border-primary/50 transition-all cursor-pointer pr-10 focus:outline-none focus:ring-1 focus:ring-primary/30"
            >
              {CURRENCIES.map(c => (
                <option key={c.code} value={c.code}>{c.label}</option>
              ))}
            </select>
            <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-outline pointer-events-none text-sm">language</span>
          </div>

          <button className="px-4 py-2 border border-outline-variant/30 text-on-surface text-sm font-medium rounded-lg hover:bg-surface-container-high transition-colors flex items-center gap-2">
            <span className="material-symbols-outlined text-sm">download</span> Export PDF
          </button>
        </div>
      </header>

      {/* BOM Table */}
      <div className="bg-surface-container-low rounded-xl border border-outline-variant/15 overflow-hidden mb-8 shadow-sm">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-surface-container/50 border-b border-outline-variant/10">
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline">Product</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline text-center">Qty</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline text-right">Unit Price</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline text-right">Total</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline">Purpose</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/5">
            {bom.map((item, i) => {
              const unitPrice = getPrice(item.product);
              const total = unitPrice * item.qty;
              return (
                <tr key={i} className="hover:bg-surface-container transition-colors group">
                  <td className="px-6 py-4">
                    <div className="font-medium text-on-surface text-sm">{item.product}</div>
                    <div className="text-[10px] text-outline uppercase tracking-wider mt-1">{item.category}</div>
                  </td>
                  <td className="px-6 py-4 text-center text-sm font-bold text-primary">{item.qty}</td>
                  <td className="px-6 py-4 text-right text-sm text-on-surface-variant font-[family-name:var(--font-mono)]">
                    {activeCurrency.symbol}{unitPrice.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-bold text-on-surface font-[family-name:var(--font-mono)]">
                    {activeCurrency.symbol}{total.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-sm text-on-surface-variant italic opacity-70 group-hover:opacity-100 transition-opacity">
                    {item.purpose}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {/* Grand Total Footer */}
          <tfoot>
            <tr className="bg-primary/5 border-t border-primary/20">
              <td colSpan="3" className="px-6 py-4 text-right text-sm font-bold text-on-surface uppercase tracking-wider">Estimated Investment</td>
              <td className="px-6 py-4 text-right text-xl font-bold text-primary font-[family-name:var(--font-headline)]">
                {activeCurrency.symbol}{grandTotal.toLocaleString()}
              </td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Navigation */}
      <div className="flex justify-between items-center">
        <button onClick={() => navigate('/design')} className="px-6 py-3 border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:bg-surface-container-high transition-all flex items-center gap-2">
          <span className="material-symbols-outlined">arrow_back</span> Back to Design
        </button>
        <div className="flex gap-4">
          <button onClick={() => navigate('/topology')} className="px-6 py-3 border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:bg-surface-container-high transition-all flex items-center gap-2">
            Detailed Topology <span className="material-symbols-outlined">account_tree</span>
          </button>
          <button onClick={() => navigate('/deployment')} className="px-6 py-3 bg-gradient-to-r from-primary to-primary-container text-on-primary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2 shadow-lg shadow-primary/20">
            Proceed to Deployment <span className="material-symbols-outlined">arrow_forward</span>
          </button>
        </div>
      </div>
    </div>
    </div>
  );
}
