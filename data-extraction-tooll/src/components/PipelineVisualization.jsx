import React, { useCallback } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { FileText, Cpu, Database } from 'lucide-react';

// Custom node component
const CustomNode = ({ data }) => {
  const IconComponent = data.icon;
  
  return (
    <div className={`px-6 py-4 shadow-lg rounded-lg border-2 ${data.bgColor} ${data.borderColor} min-w-[200px]`}>
      <div className="flex items-center justify-center mb-2">
        <IconComponent className={`h-8 w-8 ${data.iconColor}`} />
      </div>
      <div className="text-center">
        <h3 className="font-bold text-lg text-gray-800">{data.label}</h3>
        <p className="text-sm text-gray-600 mt-1">{data.description}</p>
      </div>
      {data.status && (
        <div className={`mt-3 px-3 py-1 rounded-full text-xs font-medium text-center ${data.statusColor}`}>
          {data.status}
        </div>
      )}
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

const initialNodes = [
  {
    id: '1',
    type: 'custom',
    position: { x: 50, y: 100 },
    data: {
      label: 'Input',
      description: 'PDF/Image Upload',
      icon: FileText,
      bgColor: 'bg-blue-50',
      borderColor: 'border-blue-200',
      iconColor: 'text-blue-600',
      status: 'Ready',
      statusColor: 'bg-blue-100 text-blue-800'
    },
  },
  {
    id: '2',
    type: 'custom',
    position: { x: 350, y: 100 },
    data: {
      label: 'Processing',
      description: 'OlmOCR Extraction',
      icon: Cpu,
      bgColor: 'bg-yellow-50',
      borderColor: 'border-yellow-200',
      iconColor: 'text-yellow-600',
      status: 'Waiting',
      statusColor: 'bg-gray-100 text-gray-600'
    },
  },
  {
    id: '3',
    type: 'custom',
    position: { x: 650, y: 100 },
    data: {
      label: 'Output',
      description: 'Structured JSON Data',
      icon: Database,
      bgColor: 'bg-green-50',
      borderColor: 'border-green-200',
      iconColor: 'text-green-600',
      status: 'Pending',
      statusColor: 'bg-gray-100 text-gray-600'
    },
  },
];

const initialEdges = [
  {
    id: 'e1-2',
    source: '1',
    target: '2',
    type: 'smoothstep',
    animated: false,
    style: { stroke: '#6b7280', strokeWidth: 2 },
  },
  {
    id: 'e2-3',
    source: '2',
    target: '3',
    type: 'smoothstep',
    animated: false,
    style: { stroke: '#6b7280', strokeWidth: 2 },
  },
];

export default function PipelineVisualization({ processingStatus = 'idle' }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  // Update node status based on processing state
  React.useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        let updatedData = { ...node.data };
        
        switch (processingStatus) {
          case 'uploading':
            if (node.id === '1') {
              updatedData.status = 'Uploading';
              updatedData.statusColor = 'bg-blue-100 text-blue-800';
            }
            break;
          case 'processing':
            if (node.id === '1') {
              updatedData.status = 'Complete';
              updatedData.statusColor = 'bg-green-100 text-green-800';
            }
            if (node.id === '2') {
              updatedData.status = 'Processing';
              updatedData.statusColor = 'bg-yellow-100 text-yellow-800';
            }
            break;
          case 'complete':
            if (node.id === '1') {
              updatedData.status = 'Complete';
              updatedData.statusColor = 'bg-green-100 text-green-800';
            }
            if (node.id === '2') {
              updatedData.status = 'Complete';
              updatedData.statusColor = 'bg-green-100 text-green-800';
            }
            if (node.id === '3') {
              updatedData.status = 'Complete';
              updatedData.statusColor = 'bg-green-100 text-green-800';
            }
            break;
          case 'error':
            if (node.id === '2') {
              updatedData.status = 'Error';
              updatedData.statusColor = 'bg-red-100 text-red-800';
            }
            break;
          default:
            // Reset to initial state
            if (node.id === '1') {
              updatedData.status = 'Ready';
              updatedData.statusColor = 'bg-blue-100 text-blue-800';
            }
            if (node.id === '2') {
              updatedData.status = 'Waiting';
              updatedData.statusColor = 'bg-gray-100 text-gray-600';
            }
            if (node.id === '3') {
              updatedData.status = 'Pending';
              updatedData.statusColor = 'bg-gray-100 text-gray-600';
            }
        }
        
        return { ...node, data: updatedData };
      })
    );

    // Update edge animation based on processing status
    setEdges((eds) =>
      eds.map((edge) => {
        let animated = false;
        
        if (processingStatus === 'processing') {
          if (edge.id === 'e1-2') {
            animated = true;
          }
        } else if (processingStatus === 'complete') {
          animated = false;
        }
        
        return { ...edge, animated };
      })
    );
  }, [processingStatus, setNodes, setEdges]);

  return (
    <div className="h-80 w-full border border-gray-200 rounded-lg bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
      >
        <Controls />
        <MiniMap />
        <Background variant="dots" gap={12} size={1} />
      </ReactFlow>
    </div>
  );
}

